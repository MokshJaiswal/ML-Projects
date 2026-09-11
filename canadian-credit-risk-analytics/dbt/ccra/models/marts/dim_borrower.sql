-- Borrower dimension. One row per borrower; attributes are as-at origination,
-- which is the standard convention for credit portfolio reporting.

select
    borrower_id                                             as borrower_key,
    borrower_id,
    province_code,
    province_name,
    cma_name,
    {{ dbt_utils_surrogate_key(['province_code', 'cma_name']) }} as geography_key,
    credit_score_at_origination,
    credit_risk_band,
    annual_income_cad,
    income_band,
    age_band,
    employment_type,
    is_newcomer
from {{ ref('stg_borrowers') }}
