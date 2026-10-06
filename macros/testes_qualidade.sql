{# ---- Testes genéricos que implementam as cláusulas de qualidade dos contratos ---- #}

{% test positivo(model, column_name) %}
select {{ column_name }} from {{ model }} where {{ column_name }} <= 0
{% endtest %}

{# Ticket médio por dia fora da faixa combinada: pega troca silenciosa de unidade (reais -> centavos). #}
{% test ticket_medio_diario_entre(model, coluna, coluna_data, minimo, maximo) %}
select cast({{ coluna_data }} as date) as dia, avg({{ coluna }}) as ticket_medio
from {{ model }}
group by 1
having avg({{ coluna }}) < {{ minimo }} or avg({{ coluna }}) > {{ maximo }}
{% endtest %}

{# Dia com volume abaixo de uma fração da mediana: pega carga parcial ou arquivo truncado. #}
{% test volume_diario_minimo(model, coluna_data, fracao_da_mediana) %}
with por_dia as (
    select cast({{ coluna_data }} as date) as dia, count(*) as n from {{ model }} group by 1
), ref as (select median(n) as mediana from por_dia)
select dia, n, mediana from por_dia, ref where n < {{ fracao_da_mediana }} * mediana
{% endtest %}

{# CPF com 11 dígitos e dígitos verificadores corretos. #}
{% test cpf_valido(model, column_name) %}
with base as (
    select {{ column_name }} as cpf from {{ model }} where {{ column_name }} is not null
), calc as (
    select cpf,
        (select sum(cast(substr(cpf, i, 1) as int) * (11 - i)) from range(1, 10) t(i)) as s1,
        (select sum(cast(substr(cpf, i, 1) as int) * (12 - i)) from range(1, 11) t(i)) as s2
    from base where regexp_full_match(cpf, '[0-9]{11}')
)
select cpf from base where not regexp_full_match(cpf, '[0-9]{11}')
union all
select cpf from calc
where cast(substr(cpf, 10, 1) as int) <> (case when (s1 * 10) % 11 = 10 then 0 else (s1 * 10) % 11 end)
   or cast(substr(cpf, 11, 1) as int) <> (case when (s2 * 10) % 11 = 10 then 0 else (s2 * 10) % 11 end)
{% endtest %}

{% test formato(model, column_name, regex) %}
select {{ column_name }} from {{ model }}
where {{ column_name }} is not null and not regexp_full_match({{ column_name }}, '{{ regex }}')
{% endtest %}

{# Finalidade: todo contato do mart de CRM precisa ter consentimento vigente na origem. #}
{% test somente_com_consentimento(model) %}
select m.id_cliente
from {{ model }} m
left join {{ ref('silver_clientes') }} c using (id_cliente)
where c.id_cliente is null or not c.consentimento_marketing_ativo or c.status_cliente <> 'ativo'
{% endtest %}

{# Varre TODAS as colunas de texto da view procurando padrões de identificador direto.
   Não confia na política: confere o dado que sai de fato. #}
{% test nao_expoe_identificadores(model) %}
{%- set cols = adapter.get_columns_in_relation(model) if execute else [] -%}
{%- set texto = cols | selectattr('dtype', 'in', ['VARCHAR', 'TEXT', 'STRING']) | list -%}
{%- if texto | length == 0 %}
select 1 as nada where false
{%- else %}
{%- for c in texto %}
select '{{ c.name }}' as coluna, cast({{ adapter.quote(c.name) }} as varchar) as valor
from {{ model }}
where regexp_full_match(cast({{ adapter.quote(c.name) }} as varchar), '[0-9]{10,11}')                      -- CPF / telefone só dígitos
   or regexp_matches(cast({{ adapter.quote(c.name) }} as varchar), '[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}') -- CPF formatado
   or regexp_matches(cast({{ adapter.quote(c.name) }} as varchar), '[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]+\.[a-z]{2,}') -- e-mail
{% if not loop.last %}union all{% endif %}
{%- endfor %}
{%- endif %}
{% endtest %}
