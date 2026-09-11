-- Pre-aggregated portfolio summary by month / product / province.
--
-- The fact table is 3M rows, which Power BI handles comfortably, but a summary
-- at the grain every executive page actually uses makes the landing page render
-- instantly. Detail pages still drill through to the full fact.

select
    f.date_key                                              as snapshot_month,
    p.product_name,
    p.product_category,
    a.province_code,
    a.origination_rate_era,
    a.credit_risk_band,

    count(*)                                                as account_count,
    sum(f.balance_cad)                                      as total_balance_cad,
    sum(f.delinquent_balance_cad)                           as delinquent_balance_cad,
    sum(f.impaired_balance_cad)                             as impaired_balance_cad,
    sum(f.defaulted_balance_cad)                            as defaulted_balance_cad,
    sum(f.expected_loss_cad)                                as expected_loss_cad,
    sum(f.delinquent_account_count)                         as delinquent_account_count,
    sum(f.impaired_account_count)                           as impaired_account_count,

    avg(f.interest_rate_pct)                                as avg_interest_rate_pct,
    avg(f.monthly_pd)                                       as avg_monthly_pd,
    avg(f.unemployment_rate_pct)                            as avg_unemployment_rate_pct,
    sum(case when f.has_renewed then f.balance_cad else 0 end) as renewed_balance_cad,
    avg(case when f.has_renewed then f.payment_shock_pct end)  as avg_payment_shock_pct
from {{ ref('fact_account_month') }} f
inner join {{ ref('dim_account') }} a on a.account_key = f.account_key
inner join {{ ref('dim_product') }} p on p.product_key = f.product_key
group by 1, 2, 3, 4, 5, 6
