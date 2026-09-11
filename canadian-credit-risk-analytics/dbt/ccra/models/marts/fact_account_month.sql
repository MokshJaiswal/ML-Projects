-- The central fact. Grain: one row per account per reporting month.
--
-- Additive measures (balance, expected loss) are stored raw so Power BI can sum
-- them across any dimension. Ratios are deliberately NOT stored: they are
-- defined as DAX measures so they stay correct under every filter context.
-- Pre-computing a rate here would break the moment someone slices it.

select
    f.account_id                                            as account_key,
    f.snapshot_month                                        as date_key,
    a.borrower_key,
    a.product_key,
    a.geography_key,

    f.months_on_book,
    f.balance_cad,
    f.scheduled_payment_cad,
    f.interest_rate_pct,
    f.payment_shock_pct,
    f.payment_shock_band,
    f.has_renewed,

    f.delinquency_state,
    f.days_past_due_bucket,
    f.is_delinquent,
    f.is_impaired,
    f.is_default,

    f.monthly_pd,
    f.expected_loss_cad,
    f.unemployment_rate_pct,

    -- Additive numerators. Storing these as 0/1-weighted amounts lets every
    -- rate in the dashboard be a simple DIVIDE of two SUMs.
    case when f.is_delinquent then f.balance_cad else 0 end as delinquent_balance_cad,
    case when f.is_impaired   then f.balance_cad else 0 end as impaired_balance_cad,
    case when f.is_default    then f.balance_cad else 0 end as defaulted_balance_cad,
    case when f.is_delinquent then 1 else 0 end             as delinquent_account_count,
    case when f.is_impaired   then 1 else 0 end             as impaired_account_count,
    1                                                       as account_count
from {{ ref('stg_account_month') }} f
inner join {{ ref('dim_account') }} a on a.account_id = f.account_id
