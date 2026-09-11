"""Loan-level portfolio simulator driven by the macro scenario.

No Canadian lender publishes account-level performance, so the portfolio is
simulated. What makes it analytically useful rather than arbitrary is that every
account's monthly default hazard is a function of the *actual macro series
ingested upstream*: when the policy rate path moves, renewal payment shock moves
with it, and delinquency follows. Swap in live Bank of Canada data and the
portfolio responds.

Three tables are produced:

``borrowers``            one row per borrower
``accounts``             one row per credit facility
``account_month``        one row per account per month (the fact grain)

The generator is seeded, so a given config yields a byte-identical portfolio.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ccra.logging_setup import get_logger, stage

log = get_logger("ccra.simulate")

# Delinquency states. Index order matters: the roll-forward walks it.
STATES = ["CURRENT", "DPD_30", "DPD_60", "DPD_90", "DPD_120", "DEFAULT"]
S_CURRENT, S_30, S_60, S_90, S_120, S_DEFAULT = range(6)

PROVINCE_GEO = {
    "ON": "Ontario", "BC": "British Columbia", "AB": "Alberta", "QC": "Quebec",
    "MB": "Manitoba", "SK": "Saskatchewan", "NS": "Nova Scotia", "NB": "New Brunswick",
}

# Product shape: (term_months, amortization_months, is_amortising, is_revolving,
#                 is_renewable)
#
# ``is_renewable`` distinguishes a facility whose *term* is shorter than its
# *amortisation* — a Canadian mortgage amortises over 25 years but the contract
# rate is only fixed for 5, so it reprices at renewal. An auto loan amortises
# fully over its term: it matures, it never reprices. Conflating the two
# produces a fictitious payment shock on auto.
PRODUCT_TERMS = {
    "MORTGAGE_FIXED_5Y": (60, 300, True, False, True),
    "MORTGAGE_VARIABLE": (60, 300, True, False, True),
    "HELOC":             (0, 0, False, True, False),
    "AUTO":              (72, 72, True, False, False),
    "CREDIT_CARD":       (0, 0, False, True, False),
}


def _amortising_payment(principal: np.ndarray, annual_rate: np.ndarray, n_months: np.ndarray) -> np.ndarray:
    """Standard level-payment amortisation.

    Canadian fixed mortgages compound semi-annually; we use the simpler monthly
    convention here and document the simplification rather than hide it.
    """
    r = annual_rate / 100.0 / 12.0
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(
            r > 0,
            r / (1.0 - np.power(1.0 + r, -n_months)),
            1.0 / np.maximum(n_months, 1),
        )
    return principal * factor


def _macro_lookup(macro: pd.DataFrame, metric: str, geo: str | None = None) -> pd.Series:
    """Return a month-indexed series for one metric, forward-filled."""
    sel = macro[macro["metric"] == metric]
    if geo is not None:
        sel = sel[sel["geo"] == geo]
    if sel.empty:
        raise ValueError(f"macro series not found: metric={metric} geo={geo}")
    s = (
        sel.set_index("observation_date")["value"]
        .sort_index()
        .groupby(level=0).last()
        .resample("MS").ffill()
    )
    return s


def generate_borrowers(cfg, rng: np.random.Generator) -> pd.DataFrame:
    """Create the borrower dimension with realistic regional and credit mix."""
    pcfg = cfg.portfolio
    n = int(pcfg["n_borrowers"])
    regions = pcfg["regions"]

    provinces = list(regions)
    shares = np.array([regions[p]["share"] for p in provinces], dtype=float)
    prov = rng.choice(provinces, size=n, p=shares / shares.sum())

    # CMA within the drawn province.
    cma = np.empty(n, dtype=object)
    for p in provinces:
        mask = prov == p
        choices = regions[p]["cma"]
        cma[mask] = rng.choice(choices, size=int(mask.sum()))

    score_cfg = pcfg["credit_score"]
    score = rng.normal(score_cfg["mean"], score_cfg["sd"], n)
    score = np.clip(score, score_cfg["floor"], score_cfg["ceiling"]).round().astype(int)

    # Income is lognormal and mildly correlated with score.
    base_income = rng.lognormal(mean=11.28, sigma=0.46, size=n)
    income = base_income * (1.0 + 0.30 * (score - score_cfg["mean"]) / score_cfg["sd"])
    income = np.clip(income, 24_000, 750_000).round(-2)

    age_band = rng.choice(
        ["18-29", "30-39", "40-49", "50-59", "60+"],
        size=n, p=[0.16, 0.29, 0.24, 0.18, 0.13],
    )
    employment = rng.choice(
        ["SALARIED", "HOURLY", "SELF_EMPLOYED", "CONTRACT", "RETIRED"],
        size=n, p=[0.52, 0.20, 0.13, 0.09, 0.06],
    )
    # Newcomers are a material and growing segment of Canadian retail credit.
    newcomer = rng.random(n) < 0.14

    return pd.DataFrame(
        {
            "borrower_id": np.arange(1, n + 1),
            "province_code": prov,
            "province_name": [PROVINCE_GEO.get(p, p) for p in prov],
            "cma_name": cma,
            "credit_score_at_origination": score,
            "annual_income_cad": income,
            "age_band": age_band,
            "employment_type": employment,
            "is_newcomer": newcomer,
        }
    )


def generate_accounts(cfg, borrowers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Create credit facilities, including origination vintage and renewal dates.

    Origination vintage is the analytical crux: accounts written in the
    low-rate era carry a below-market contract rate until their renewal date,
    at which point the payment resets to prevailing rates.
    """
    pcfg = cfg.portfolio
    mix = pcfg["product_mix"]
    products = list(mix)
    probs = np.array([mix[p] for p in products], dtype=float)

    n_borrowers = len(borrowers)
    # Primary account for everyone, plus a second product for some.
    holders = np.arange(n_borrowers)
    extra = holders[rng.random(n_borrowers) < pcfg["multi_product_rate"]]
    owner_idx = np.concatenate([holders, extra])
    n = len(owner_idx)

    product = rng.choice(products, size=n, p=probs / probs.sum())

    orig_start = pd.Timestamp(cfg.window["origination_start"])
    obs_end = pd.Timestamp(cfg.window["observation_end"])
    span_days = (obs_end - orig_start).days

    # Originations skew toward the low-rate era (2020-2021), which is what
    # creates the renewal wave under study.
    u = rng.beta(a=2.1, b=2.6, size=n)
    orig_offset = (u * span_days).astype(int)
    origination_date = orig_start + pd.to_timedelta(orig_offset, unit="D")
    origination_date = origination_date.to_period("M").to_timestamp()

    b = borrowers.iloc[owner_idx].reset_index(drop=True)
    income = b["annual_income_cad"].to_numpy()
    score = b["credit_score_at_origination"].to_numpy()

    # Size the facility off income, with product-specific multiples.
    multiple = np.select(
        [
            np.isin(product, ["MORTGAGE_FIXED_5Y", "MORTGAGE_VARIABLE"]),
            product == "HELOC",
            product == "AUTO",
            product == "CREDIT_CARD",
        ],
        [
            rng.uniform(3.0, 5.6, n),
            rng.uniform(0.4, 1.3, n),
            rng.uniform(0.25, 0.75, n),
            rng.uniform(0.05, 0.22, n),
        ],
        default=1.0,
    )
    original_balance = np.round(income * multiple, -2)
    original_balance = np.clip(original_balance, 1_500, 2_200_000)

    # Contract rate at origination: cheap money early, expensive later.
    years_from_start = (origination_date.year - orig_start.year) + (origination_date.month - 1) / 12.0
    era_rate = np.interp(years_from_start, [0, 1, 2, 3, 4, 5, 6, 7], [3.3, 3.1, 1.9, 2.1, 4.6, 5.9, 5.4, 4.8])
    spread = np.select(
        [
            product == "MORTGAGE_FIXED_5Y",
            product == "MORTGAGE_VARIABLE",
            product == "HELOC",
            product == "AUTO",
            product == "CREDIT_CARD",
        ],
        [0.0, -0.35, 1.10, 3.20, 16.50],
        default=0.0,
    )
    # Better credit prices tighter.
    credit_adj = -0.9 * (score - 700) / 100.0
    original_rate = np.clip(era_rate + spread + credit_adj + rng.normal(0, 0.18, n), 0.9, 29.99)

    term, amort, is_amort, is_revolving, is_renewable = (
        np.array([PRODUCT_TERMS[p][i] for p in product]) for i in range(5)
    )
    is_amort = is_amort.astype(bool)
    is_revolving = is_revolving.astype(bool)
    is_renewable = is_renewable.astype(bool)

    renewal_date = pd.Series(origination_date) + pd.to_timedelta(term * 30.44, unit="D")
    renewal_date = renewal_date.dt.to_period("M").dt.to_timestamp()
    # Only renewable facilities carry a renewal date; everything else matures.
    renewal_date = renewal_date.where(is_renewable, pd.NaT)

    is_mortgage = np.isin(product, ["MORTGAGE_FIXED_5Y", "MORTGAGE_VARIABLE"])
    ltv = np.where(is_mortgage, np.clip(rng.normal(0.74, 0.11, n), 0.35, 0.95), np.nan)
    property_value = np.where(is_mortgage, np.round(original_balance / np.where(np.isnan(ltv), 1, ltv), -2), np.nan)

    payment = np.where(
        is_amort,
        _amortising_payment(original_balance, original_rate, np.maximum(amort, 1)),
        original_balance * 0.03,   # revolving: 3% minimum payment
    )
    # Total debt service ratio against monthly income.
    tds = np.clip(payment * 12.0 / np.maximum(income, 1) + rng.uniform(0.04, 0.16, n), 0.05, 0.85)

    return pd.DataFrame(
        {
            "account_id": np.arange(1, n + 1),
            "borrower_id": b["borrower_id"].to_numpy(),
            "product_code": product,
            "origination_date": origination_date,
            "renewal_date": renewal_date.to_numpy(),
            "term_months": term,
            "amortization_months": amort,
            "is_amortising": is_amort,
            "is_revolving": is_revolving,
            "is_renewable": is_renewable,
            "original_balance_cad": original_balance,
            "original_rate_pct": np.round(original_rate, 3),
            "original_payment_cad": np.round(payment, 2),
            "ltv_at_origination": np.round(ltv, 4),
            "property_value_cad": property_value,
            "tds_at_origination": np.round(tds, 4),
        }
    )


def simulate_account_months(cfg, accounts: pd.DataFrame, borrowers: pd.DataFrame,
                            macro: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Walk the portfolio month by month through a delinquency state machine.

    Each month an account may deteriorate (driven by a logistic hazard) or cure.
    ``DEFAULT`` is absorbing. Payment shock is recomputed at each renewal against
    the prevailing market rate taken from the macro table.
    """
    rcfg = cfg.risk
    coef = rcfg["coefficients"]
    months = pd.date_range(
        cfg.window["observation_start"], cfg.window["observation_end"], freq="MS"
    )

    market_rate = _macro_lookup(macro, "conventional_5y", "Canada").reindex(months).ffill().bfill()
    unemployment = {
        prov: _macro_lookup(macro, "unemployment_rate", geo).reindex(months).ffill().bfill()
        for prov, geo in PROVINCE_GEO.items()
        if geo in set(macro.loc[macro["metric"] == "unemployment_rate", "geo"])
    }
    national_unemp = pd.concat(unemployment.values(), axis=1).mean(axis=1) if unemployment else pd.Series(6.0, index=months)

    acct = accounts.merge(
        borrowers[["borrower_id", "province_code", "annual_income_cad"]],
        on="borrower_id", how="left",
    )
    n = len(acct)

    product = acct["product_code"].to_numpy()
    orig_date = acct["origination_date"].to_numpy()
    renewal = acct["renewal_date"].to_numpy()
    balance = acct["original_balance_cad"].to_numpy(dtype=float).copy()
    rate = acct["original_rate_pct"].to_numpy(dtype=float).copy()
    payment = acct["original_payment_cad"].to_numpy(dtype=float).copy()
    orig_payment = acct["original_payment_cad"].to_numpy(dtype=float)
    amort = acct["amortization_months"].to_numpy(dtype=float)
    is_amort = acct["is_amortising"].to_numpy(dtype=bool)
    score = borrowers.set_index("borrower_id").loc[acct["borrower_id"], "credit_score_at_origination"].to_numpy()
    ltv = np.nan_to_num(acct["ltv_at_origination"].to_numpy(dtype=float), nan=0.55)
    tds = acct["tds_at_origination"].to_numpy(dtype=float)
    prov = acct["province_code"].to_numpy()

    intercepts = np.array([rcfg["product_intercept"][p] for p in product])
    lgd = np.array([rcfg["loss_given_default"][p] for p in product])
    cure = rcfg["cure_rate"]
    cure_vec = np.array([0.0, cure["DPD_30"], cure["DPD_60"], cure["DPD_90"], cure["DPD_120"], 0.0])

    state = np.zeros(n, dtype=np.int8)
    has_renewed = np.zeros(n, dtype=bool)
    payment_shock = np.zeros(n, dtype=float)

    frames: list[pd.DataFrame] = []
    base_hazard = float(rcfg["base_monthly_hazard"])
    base_logit = np.log(base_hazard / (1 - base_hazard))

    for month in months:
        active = (orig_date <= np.datetime64(month)) & (state != S_DEFAULT) & (balance > 0)
        if not active.any():
            continue

        # -- renewal repricing -------------------------------------------
        due = active & (~has_renewed) & (~pd.isna(renewal)) & (renewal <= np.datetime64(month))
        if due.any():
            new_rate = float(market_rate.loc[month])
            remaining = np.maximum(amort[due] - _months_between(orig_date[due], month), 12)
            new_payment = _amortising_payment(balance[due], np.full(due.sum(), new_rate), remaining)
            payment_shock[due] = new_payment / np.maximum(orig_payment[due], 1e-6) - 1.0
            payment[due] = new_payment
            rate[due] = new_rate
            has_renewed[due] = True

        mob = _months_between(orig_date, month)
        unemp = np.array([
            float(unemployment[p].loc[month]) if p in unemployment else float(national_unemp.loc[month])
            for p in prov
        ])

        # -- monthly default hazard --------------------------------------
        logit = (
            base_logit
            + intercepts
            + coef["credit_score_per_100"] * (score - 700) / 100.0
            + coef["ltv_per_10pct"] * (ltv - 0.70) * 10.0
            + coef["tds_per_10pct"] * (tds - 0.35) * 10.0
            + coef["payment_shock_per_10pct"] * payment_shock * 10.0
            + coef["unemployment_per_1pct"] * (unemp - 6.0)
            + coef["months_on_book_per_12"] * (mob / 12.0)
        )
        hazard = 1.0 / (1.0 + np.exp(-logit))

        # Roll-rate transitions, the standard formulation used in credit risk:
        #   CURRENT    -> enters delinquency with probability `hazard`
        #   DELINQUENT -> cures with probability cure_rate[state],
        #                 otherwise rolls forward one bucket
        # Requiring a fresh hazard draw to advance an already-delinquent account
        # would let accounts sit at 30 DPD indefinitely and defaults would never
        # materialise.
        is_current = active & (state == S_CURRENT)
        is_delinquent = active & (state > S_CURRENT) & (state < S_DEFAULT)

        entering = is_current & (rng.random(n) < hazard)
        curing = is_delinquent & (rng.random(n) < cure_vec[state])
        rolling = is_delinquent & ~curing

        state = np.where(entering, S_30, state)
        state = np.where(curing, S_CURRENT, state)
        state = np.where(rolling, np.minimum(state + 1, S_DEFAULT), state)

        # -- balance amortisation ----------------------------------------
        paying = active & (state <= S_30)
        interest = balance * rate / 100.0 / 12.0
        principal = np.where(is_amort, np.maximum(payment - interest, 0.0), balance * 0.018)
        balance = np.where(paying, np.maximum(balance - principal, 0.0), balance + np.where(active, interest, 0.0))

        expected_loss = np.where(state >= S_90, balance * lgd, balance * hazard * lgd * 12)

        frames.append(
            pd.DataFrame(
                {
                    "account_id": acct["account_id"].to_numpy()[active],
                    "snapshot_month": month,
                    "months_on_book": mob[active].astype(int),
                    "balance_cad": np.round(balance[active], 2),
                    "scheduled_payment_cad": np.round(payment[active], 2),
                    "interest_rate_pct": np.round(rate[active], 3),
                    "payment_shock_pct": np.round(payment_shock[active], 4),
                    "has_renewed": has_renewed[active],
                    "delinquency_state": [STATES[s] for s in state[active]],
                    "days_past_due_bucket": np.array(
                        ["0", "1-29", "30-59", "60-89", "90-119", "120+"]
                    )[state[active]],
                    "is_default": (state[active] == S_DEFAULT),
                    "monthly_pd": np.round(hazard[active], 6),
                    "expected_loss_cad": np.round(expected_loss[active], 2),
                    "unemployment_rate_pct": np.round(unemp[active], 2),
                }
            )
        )

    out = pd.concat(frames, ignore_index=True)
    log.info(
        "simulated %d account-months across %d months; terminal default rate %.2f%%",
        len(out), len(months), 100.0 * (state == S_DEFAULT).mean(),
    )
    return out


def _months_between(start, month) -> np.ndarray:
    """Whole months from each ``start`` datetime64 to ``month``."""
    s = pd.DatetimeIndex(pd.Series(start))
    return ((month.year - s.year) * 12 + (month.month - s.month)).to_numpy().clip(min=0)


def run(cfg, macro: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Stage entry point: build all three portfolio tables and persist them."""
    rng = np.random.default_rng(cfg.portfolio["seed"])
    staged = Path(cfg.path("staged"))
    staged.mkdir(parents=True, exist_ok=True)

    with stage(log, "simulate_portfolio") as st:
        borrowers = generate_borrowers(cfg, rng)
        accounts = generate_accounts(cfg, borrowers, rng)
        account_month = simulate_account_months(cfg, accounts, borrowers, macro, rng)

        borrowers.to_parquet(staged / "borrowers.parquet", index=False)
        accounts.to_parquet(staged / "accounts.parquet", index=False)
        account_month.to_parquet(staged / "account_month.parquet", index=False)

        st["borrowers"] = len(borrowers)
        st["accounts"] = len(accounts)
        st["account_months"] = len(account_month)

    return {"borrowers": borrowers, "accounts": accounts, "account_month": account_month}
