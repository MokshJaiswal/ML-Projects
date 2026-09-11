-- The analysis this project exists to answer.
--
-- For every renewable facility that has not yet repriced, estimate the payment
-- it will reset to at prevailing market rates, the resulting payment shock, and
-- the incremental expected loss that shock implies. This is the table the
-- executive recommendation is built from.

with market_rate as (
    -- Latest observed market rate, used as the repricing assumption.
    select conventional_5y_rate_pct, observation_month
    from {{ ref('stg_macro') }}
    where conventional_5y_rate_pct is not null
    qualify row_number() over (order by observation_month desc) = 1
),

current_book as (
    select f.*
    from {{ ref('fact_account_month') }} f
    inner join {{ ref('dim_date') }} d on d.date_key = f.date_key
    where d.is_current_month
),

upcoming as (
    select
        cb.account_key,
        a.account_id,
        a.product_key,
        a.province_code,
        a.cma_name,
        a.credit_risk_band,
        a.income_band,
        a.origination_rate_era,
        a.ltv_band,
        a.renewal_date,
        a.original_rate_pct,
        cb.balance_cad,
        cb.scheduled_payment_cad                            as current_payment_cad,
        cb.interest_rate_pct                                as current_rate_pct,
        a.amortization_months,
        cb.months_on_book,
        (select conventional_5y_rate_pct from market_rate)  as assumed_renewal_rate_pct,
        cb.monthly_pd,
        cb.delinquency_state
    from current_book cb
    inner join {{ ref('dim_account') }} a on a.account_key = cb.account_key
    where a.is_renewable
      and not cb.has_renewed
      and cb.balance_cad > 0
),

repriced as (
    select
        *,
        greatest(amortization_months - months_on_book, 12)  as remaining_amort_months,
        assumed_renewal_rate_pct / 100.0 / 12.0             as monthly_rate
    from upcoming
),

calculated as (
    select
        *,
        -- Level-payment amortisation at the assumed renewal rate.
        balance_cad * (
            monthly_rate / (1 - power(1 + monthly_rate, -remaining_amort_months))
        )                                                   as projected_payment_cad
    from repriced
)

select
    account_key,
    account_id,
    product_key,
    province_code,
    cma_name,
    credit_risk_band,
    income_band,
    origination_rate_era,
    ltv_band,
    renewal_date,
    date_trunc('quarter', renewal_date)                     as renewal_quarter,
    balance_cad,
    original_rate_pct,
    current_rate_pct,
    assumed_renewal_rate_pct,
    current_payment_cad,
    round(projected_payment_cad, 2)                         as projected_payment_cad,
    round(projected_payment_cad - current_payment_cad, 2)   as payment_increase_cad,
    round(projected_payment_cad / nullif(current_payment_cad, 0) - 1, 4)
                                                            as projected_payment_shock_pct,
    case
        when projected_payment_cad / nullif(current_payment_cad, 0) - 1 > 0.40 then 'SEVERE_OVER_40'
        when projected_payment_cad / nullif(current_payment_cad, 0) - 1 > 0.25 then 'HIGH_25_40'
        when projected_payment_cad / nullif(current_payment_cad, 0) - 1 > 0.10 then 'MODERATE_10_25'
        when projected_payment_cad / nullif(current_payment_cad, 0) - 1 > 0    then 'MILD_0_10'
        else 'NONE_OR_BENEFIT'
    end                                                     as projected_shock_band,
    monthly_pd                                              as current_monthly_pd,
    delinquency_state
from calculated
