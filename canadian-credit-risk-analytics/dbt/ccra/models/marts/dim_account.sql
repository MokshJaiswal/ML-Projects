-- Account dimension, enriched with the borrower attributes that reports filter
-- on most often. Denormalising these onto the account keeps the Power BI model
-- a clean star rather than a snowflake, which materially improves DAX
-- performance on a model this size.

select
    a.account_id                                            as account_key,
    a.account_id,
    a.borrower_id                                           as borrower_key,
    a.product_code                                          as product_key,
    {{ dbt_utils_surrogate_key(['b.province_code', 'b.cma_name']) }} as geography_key,

    a.origination_date,
    a.origination_vintage_year,
    a.origination_rate_era,
    a.renewal_date,
    a.term_months,
    a.amortization_months,
    a.is_amortising,
    a.is_revolving,
    a.is_renewable,

    a.original_balance_cad,
    a.original_rate_pct,
    a.original_payment_cad,
    a.ltv_at_origination,
    a.ltv_band,
    a.property_value_cad,
    a.tds_at_origination,

    b.credit_risk_band,
    b.income_band,
    b.employment_type,
    b.is_newcomer,
    b.province_code,
    b.cma_name
from {{ ref('stg_accounts') }} a
left join {{ ref('stg_borrowers') }} b using (borrower_id)
