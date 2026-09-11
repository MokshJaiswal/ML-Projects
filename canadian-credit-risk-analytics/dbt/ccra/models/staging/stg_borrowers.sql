with source as (
    select * from {{ source('landing', 'raw_borrowers') }}
)

select
    cast(borrower_id as bigint)                     as borrower_id,
    province_code,
    province_name,
    cma_name,
    cast(credit_score_at_origination as integer)    as credit_score_at_origination,
    cast(annual_income_cad as double)               as annual_income_cad,
    age_band,
    employment_type,
    cast(is_newcomer as boolean)                    as is_newcomer,

    -- Risk banding used across every report, defined once here so the mart,
    -- the dashboard and the AI analyst all agree on what "prime" means.
    case
        when credit_score_at_origination >= 800 then 'A_SUPER_PRIME'
        when credit_score_at_origination >= 720 then 'B_PRIME'
        when credit_score_at_origination >= 660 then 'C_NEAR_PRIME'
        when credit_score_at_origination >= 600 then 'D_SUBPRIME'
        else 'E_DEEP_SUBPRIME'
    end                                             as credit_risk_band,

    case
        when annual_income_cad < 50000  then 'UNDER_50K'
        when annual_income_cad < 90000  then '50K_90K'
        when annual_income_cad < 150000 then '90K_150K'
        else 'OVER_150K'
    end                                             as income_band
from source
