-- Macro indicators, pivoted to one row per month per geography.
-- Keeping provenance on the row means a dashboard can warn when it is showing
-- scenario data rather than published statistics.

with source as (
    select * from {{ source('landing', 'raw_macro') }}
),

typed as (
    select
        cast(observation_date as date)              as observation_month,
        geo                                         as geography_name,
        metric,
        cast(value as double)                       as metric_value,
        source                                      as data_source
    from source
)

select
    observation_month,
    geography_name,
    max(case when metric = 'policy_rate'             then metric_value end) as policy_rate_pct,
    max(case when metric = 'prime_rate'              then metric_value end) as prime_rate_pct,
    max(case when metric = 'gov_5y_yield'            then metric_value end) as gov_5y_yield_pct,
    max(case when metric = 'conventional_5y'         then metric_value end) as conventional_5y_rate_pct,
    max(case when metric = 'unemployment_rate'       then metric_value end) as unemployment_rate_pct,
    max(case when metric = 'new_housing_price_index' then metric_value end) as house_price_index,
    min(data_source)                                                        as data_source
from typed
group by 1, 2
