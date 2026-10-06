{# ============================================================================================
   Funções de privacidade. Cada uma recebe uma expressão SQL e devolve outra expressão SQL.
   ============================================================================================ #}

{# Pseudônimo estável: o mesmo valor gera sempre o mesmo pseudônimo (joins continuam
   funcionando), mas sem o segredo não dá para voltar ao valor original.
   O segredo vem da variável de ambiente ARGOS_SEGREDO (no CI, um secret do GitHub). #}
{% macro pseudonimizar(expr) -%}
    'p_' || left(sha256('{{ env_var("ARGOS_SEGREDO", "segredo-local-de-desenvolvimento") }}' || cast({{ expr }} as varchar)), 16)
{%- endmacro %}

{% macro mascarar(expr, tipo) -%}
    {%- if tipo == 'cpf' -%}
        '***.' || substr({{ expr }}, 4, 3) || '.' || substr({{ expr }}, 7, 3) || '-**'
    {%- elif tipo == 'email' -%}
        left({{ expr }}, 1) || '***@' || split_part({{ expr }}, '@', 2)
    {%- elif tipo == 'telefone' -%}
        '(' || left({{ expr }}, 2) || ') *****-' || right({{ expr }}, 4)
    {%- elif tipo == 'nome' -%}
        split_part({{ expr }}, ' ', 1) || ' ***'
    {%- else -%}
        {{ exceptions.raise_compiler_error("Não sei mascarar o tipo '" ~ tipo ~ "'. Use outro tratamento na política.") }}
    {%- endif -%}
{%- endmacro %}

{# Generalização: troca o valor exato por uma faixa (k-anonimato na prática). #}
{% macro faixa(expr, tipo) -%}
    {%- if tipo == 'data_nascimento' -%}
        case
            when date_diff('year', {{ expr }}, date '{{ var("data_referencia") }}') < 25 then '18-24'
            when date_diff('year', {{ expr }}, date '{{ var("data_referencia") }}') < 35 then '25-34'
            when date_diff('year', {{ expr }}, date '{{ var("data_referencia") }}') < 45 then '35-44'
            when date_diff('year', {{ expr }}, date '{{ var("data_referencia") }}') < 60 then '45-59'
            else '60+'
        end
    {%- elif tipo == 'renda' -%}
        case
            when {{ expr }} < 2000 then 'até 2 mil'
            when {{ expr }} < 5000 then '2 a 5 mil'
            when {{ expr }} < 10000 then '5 a 10 mil'
            when {{ expr }} < 20000 then '10 a 20 mil'
            else '20 mil+'
        end
    {%- elif tipo == 'cep' -%}
        left({{ expr }}, 3) || '**-***'
    {%- else -%}
        {{ exceptions.raise_compiler_error("Não sei gerar faixa para o tipo '" ~ tipo ~ "'.") }}
    {%- endif -%}
{%- endmacro %}

{# Lê a meta de uma coluna em qualquer versão do dbt (config.meta ou meta). #}
{% macro meta_coluna(col) -%}
    {%- set m = {} -%}
    {%- do m.update(col.get('meta', {}) or {}) -%}
    {%- do m.update((col.get('config', {}) or {}).get('meta', {}) or {}) -%}
    {{- return(m) -}}
{%- endmacro %}

{# ============================================================================================
   aplicar_politica: gera a view de um papel a partir da classificação das colunas.
   - Lê, no grafo do dbt, o tipo de dado declarado em cada coluna do modelo.
   - Consulta a matriz de política do papel (dbt_project.yml > vars.papeis).
   - Coluna sem tipo declarado => o build quebra. Tipo sem regra para o papel => coluna sai.
   ============================================================================================ #}
{% macro aplicar_politica(nome_modelo, papel) %}
    {%- set relacao = ref(nome_modelo) -%}
    {%- if not execute -%}
        select 1 as _parse
    {%- else -%}
        {%- set papeis = var('papeis') -%}
        {%- if papel not in papeis -%}
            {{ exceptions.raise_compiler_error("Papel '" ~ papel ~ "' não existe em vars.papeis.") }}
        {%- endif -%}
        {%- set politica = papeis[papel]['politica'] -%}
        {%- set tipos = var('tipos_dado') -%}
        {%- set node = (graph.nodes.values() | selectattr('resource_type', 'equalto', 'model')
                        | selectattr('name', 'equalto', nome_modelo) | first) -%}
        {%- set exprs = [] -%}
        {%- for nome_col, col in node.columns.items() -%}
            {%- set tipo = meta_coluna(col).get('tipo_dado') -%}
            {%- if tipo is none -%}
                {{ exceptions.raise_compiler_error(nome_modelo ~ "." ~ nome_col ~ " não tem tipo_dado: coluna sem classificação não é publicada.") }}
            {%- endif -%}
            {%- if tipo not in tipos -%}
                {{ exceptions.raise_compiler_error(nome_modelo ~ "." ~ nome_col ~ ": tipo_dado '" ~ tipo ~ "' não está no catálogo vars.tipos_dado.") }}
            {%- endif -%}
            {%- set trat = politica.get(tipo, 'remover') -%}
            {%- if trat == 'claro' -%}
                {%- do exprs.append(nome_col) -%}
            {%- elif trat == 'pseudonimizar' -%}
                {%- do exprs.append(pseudonimizar(nome_col) ~ ' as ' ~ nome_col) -%}
            {%- elif trat == 'mascarar' -%}
                {%- do exprs.append(mascarar(nome_col, tipo) ~ ' as ' ~ nome_col) -%}
            {%- elif trat == 'faixa' -%}
                {%- do exprs.append(faixa(nome_col, tipo) ~ ' as ' ~ nome_col ~ '_faixa') -%}
            {%- elif trat != 'remover' -%}
                {{ exceptions.raise_compiler_error("Tratamento desconhecido: " ~ trat) }}
            {%- endif -%}
        {%- endfor -%}
        {%- if exprs | length == 0 -%}
            {{ exceptions.raise_compiler_error("O papel " ~ papel ~ " não enxerga nenhuma coluna de " ~ nome_modelo) }}
        {%- endif %}
-- Gerado por aplicar_politica('{{ nome_modelo }}', '{{ papel }}'). Não edite: mude a política no dbt_project.yml.
select
    {{ exprs | join(',\n    ') }}
from {{ relacao }}
    {%- endif -%}
{% endmacro %}
