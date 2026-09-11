-- Product dimension. Small and hand-built: the grain is the product catalogue,
-- not something observed in the data, so it is declared rather than derived.

with products as (
    select distinct product_code from {{ ref('stg_accounts') }}
)

select
    product_code                                            as product_key,
    product_code,
    case product_code
        when 'MORTGAGE_FIXED_5Y' then 'Mortgage - Fixed 5 Year'
        when 'MORTGAGE_VARIABLE' then 'Mortgage - Variable'
        when 'HELOC'             then 'Home Equity Line of Credit'
        when 'AUTO'              then 'Auto Loan'
        when 'CREDIT_CARD'       then 'Credit Card'
        else product_code
    end                                                     as product_name,
    case
        when product_code like 'MORTGAGE%' then 'Real Estate Secured'
        when product_code = 'HELOC'        then 'Real Estate Secured'
        when product_code = 'AUTO'         then 'Secured Instalment'
        else 'Unsecured Revolving'
    end                                                     as product_category,
    case when product_code in ('HELOC', 'CREDIT_CARD') then true else false end
                                                            as is_revolving,
    case when product_code like 'MORTGAGE%' then true else false end
                                                            as is_renewable,
    case product_code
        when 'MORTGAGE_FIXED_5Y' then 1 when 'MORTGAGE_VARIABLE' then 2
        when 'HELOC' then 3 when 'AUTO' then 4 when 'CREDIT_CARD' then 5
        else 99
    end                                                     as display_order
from products
