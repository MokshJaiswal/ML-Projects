-- The fact grain: one row per account per reporting month.

with source as (
    select * from {{ source('landing', 'raw_account_month') }}
)

select
    cast(account_id as bigint)                      as account_id,
    cast(snapshot_month as date)                    as snapshot_month,
    cast(months_on_book as integer)                 as months_on_book,
    cast(balance_cad as double)                     as balance_cad,
    cast(scheduled_payment_cad as double)           as scheduled_payment_cad,
    cast(interest_rate_pct as double)               as interest_rate_pct,
    cast(payment_shock_pct as double)               as payment_shock_pct,
    cast(has_renewed as boolean)                    as has_renewed,
    delinquency_state,
    days_past_due_bucket,
    cast(is_default as boolean)                     as is_default,
    cast(monthly_pd as double)                      as monthly_pd,
    cast(expected_loss_cad as double)               as expected_loss_cad,
    cast(unemployment_rate_pct as double)           as unemployment_rate_pct,

    -- Regulatory-style impairment flag: 90+ days past due or defaulted.
    case when delinquency_state in ('DPD_90', 'DPD_120', 'DEFAULT')
         then true else false end                   as is_impaired,
    case when delinquency_state <> 'CURRENT'
         then true else false end                   as is_delinquent,

    case
        when payment_shock_pct <= 0      then 'NONE'
        when payment_shock_pct <= 0.10   then 'SHOCK_0_10'
        when payment_shock_pct <= 0.25   then 'SHOCK_10_25'
        when payment_shock_pct <= 0.40   then 'SHOCK_25_40'
        else 'SHOCK_OVER_40'
    end                                             as payment_shock_band
from source
