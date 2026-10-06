-- Falha se alguma coluna de modelo gold não declarar meta.tipo_dado, ou declarar um tipo
-- que não existe no catálogo. É o que impede "coluna nova chega sem dono nem classificação".
{%- set problemas = [] -%}
{%- if execute -%}
  {%- for node in graph.nodes.values() | selectattr('resource_type', 'equalto', 'model') -%}
    {%- if node.fqn[1] == 'gold' -%}
      {%- for nome_col, col in node.columns.items() -%}
        {%- set tipo = meta_coluna(col).get('tipo_dado') -%}
        {%- if tipo is none or tipo not in var('tipos_dado') -%}
          {%- do problemas.append("('" ~ node.name ~ "', '" ~ nome_col ~ "', '" ~ (tipo or 'sem tipo_dado') ~ "')") -%}
        {%- endif -%}
      {%- endfor -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif %}
{% if problemas %}
select * from (values {{ problemas | join(', ') }}) as t(modelo, coluna, problema)
{% else %}
select null as modelo, null as coluna, null as problema where false
{% endif %}
