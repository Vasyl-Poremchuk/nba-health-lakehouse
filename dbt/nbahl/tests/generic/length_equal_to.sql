{% test length_equal_to(model, column_name, expected_length) %}

    select {{ column_name }}
    from {{ model }}
    where length({{ column_name }}) <> {{ expected_length }}

{% endtest %}
