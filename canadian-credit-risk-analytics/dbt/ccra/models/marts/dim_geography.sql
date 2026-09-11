-- Geography dimension at CMA grain, carrying the latest regional macro reading
-- so regional risk can be coloured by local labour market conditions.

with base as (
    select distinct
        province_code,
        province_name,
        cma_name
    from {{ ref('stg_borrowers') }}
),

latest_macro as (
    select
        geography_name,
        unemployment_rate_pct,
        house_price_index,
        row_number() over (
            partition by geography_name order by observation_month desc
        ) as rn
    from {{ ref('stg_macro') }}
    where unemployment_rate_pct is not null
)

select
    {{ dbt_utils_surrogate_key(['base.province_code', 'base.cma_name']) }} as geography_key,
    base.province_code,
    base.province_name,
    base.cma_name,
    case base.province_code
        when 'ON' then 'Central'   when 'QC' then 'Central'
        when 'BC' then 'West'      when 'AB' then 'West'
        when 'SK' then 'Prairies'  when 'MB' then 'Prairies'
        when 'NS' then 'Atlantic'  when 'NB' then 'Atlantic'
        else 'Other'
    end                                                     as region_name,
    m.unemployment_rate_pct                                 as latest_unemployment_rate_pct,
    m.house_price_index                                     as latest_house_price_index
from base
left join latest_macro m
       on m.geography_name = base.province_name and m.rn = 1
