with source as (
    select * from {{ source('landing', 'raw_accounts') }}
)

select
    cast(account_id as bigint)                      as account_id,
    cast(borrower_id as bigint)                     as borrower_id,
    product_code,
    cast(origination_date as date)                  as origination_date,
    cast(renewal_date as date)                      as renewal_date,
    cast(term_months as integer)                    as term_months,
    cast(amortization_months as integer)            as amortization_months,
    cast(is_amortising as boolean)                  as is_amortising,
    cast(is_revolving as boolean)                   as is_revolving,
    cast(is_renewable as boolean)                   as is_renewable,
    cast(original_balance_cad as double)            as original_balance_cad,
    cast(original_rate_pct as double)               as original_rate_pct,
    cast(original_payment_cad as double)            as original_payment_cad,
    cast(ltv_at_origination as double)              as ltv_at_origination,
    cast(property_value_cad as double)              as property_value_cad,
    cast(tds_at_origination as double)              as tds_at_origination,

    date_trunc('year', origination_date)            as origination_vintage_year,
    -- The low-rate era is the cohort that carries the renewal risk.
    case
        when origination_date < date '2020-03-01' then 'PRE_PANDEMIC'
        when origination_date < date '2022-03-01' then 'LOW_RATE_ERA'
        when origination_date < date '2023-07-01' then 'TIGHTENING'
        else 'HIGH_RATE_ERA'
    end                                             as origination_rate_era,

    case
        when ltv_at_origination is null      then 'NOT_APPLICABLE'
        when ltv_at_origination > 0.80       then 'HIGH_RATIO_OVER_80'
        when ltv_at_origination > 0.65       then 'LTV_65_80'
        else 'LTV_UNDER_65'
    end                                             as ltv_band
from source
