{#
    Surrogate key generation without a package dependency.

    dbt_utils.generate_surrogate_key would do this, but pulling in a package
    means `dbt deps` needs network access on every fresh clone. This project
    only needs one macro, so it defines it locally and stays installable
    offline.

    Nulls are coalesced to a sentinel so that two rows differing only by a null
    do not collide, and parts are separated by a character that cannot appear
    in the source values.
#}
{% macro dbt_utils_surrogate_key(field_list) -%}
    md5(
        {%- for field in field_list %}
        coalesce(cast({{ field }} as varchar), '_CCRA_NULL_')
        {%- if not loop.last %} || '||' || {% endif -%}
        {%- endfor %}
    )
{%- endmacro %}
