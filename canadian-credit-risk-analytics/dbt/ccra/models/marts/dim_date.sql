-- Conformed date dimension. Power BI needs a dedicated, contiguous date table
-- marked as the model's date table for time-intelligence DAX (YTD, prior year,
-- rolling averages) to resolve correctly.

with bounds as (
    select
        min(snapshot_month) as start_month,
        max(snapshot_month) as end_month
    from {{ ref('stg_account_month') }}
),

months as (
    select unnest(generate_series(
        (select start_month from bounds),
        (select end_month from bounds),
        interval 1 month
    ))::date as date_month
)

select
    date_month                                              as date_key,
    date_month,
    extract(year  from date_month)                          as calendar_year,
    extract(month from date_month)                          as calendar_month,
    extract(quarter from date_month)                        as calendar_quarter,
    strftime(date_month, '%b %Y')                           as month_label,
    strftime(date_month, '%Y-%m')                           as year_month,
    'Q' || extract(quarter from date_month) || ' '
        || extract(year from date_month)                    as quarter_label,
    -- Canadian banks report on a 1 Nov - 31 Oct fiscal year.
    case when extract(month from date_month) >= 11
         then extract(year from date_month) + 1
         else extract(year from date_month) end             as fiscal_year,
    date_month = (select max(snapshot_month) from {{ ref('stg_account_month') }})
                                                            as is_current_month
from months
