{#
    Generic tests that would otherwise come from dbt_utils. Defined locally to
    keep the project installable without network access.
#}

{% test dbt_utils_between(model, column_name, min_value, max_value) %}
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}

{% test dbt_utils_unique_combination(model, combination_of_columns) %}
    select
        {{ combination_of_columns | join(', ') }},
        count(*) as n
    from {{ model }}
    group by {{ range(1, combination_of_columns | length + 1) | join(', ') }}
    having count(*) > 1
{% endtest %}
