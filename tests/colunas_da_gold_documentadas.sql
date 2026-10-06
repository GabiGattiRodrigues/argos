-- Confere o banco contra a documentação: toda coluna física da gold precisa estar no YAML
-- (e, portanto, classificada). Pega coluna adicionada no SQL e esquecida no YAML.
{%- set documentadas = [] -%}
{%- if execute -%}
  {%- for node in graph.nodes.values() | selectattr('resource_type', 'equalto', 'model') -%}
    {%- if node.fqn[1] == 'gold' -%}
      {%- for nome_col in node.columns -%}{%- do documentadas.append("('" ~ node.name ~ "', '" ~ nome_col ~ "')") -%}{%- endfor -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif %}
with fisicas as (
    select table_name as modelo, column_name as coluna
    from information_schema.columns
    where table_schema = 'gold'
), doc as (
    select * from (values {{ documentadas | join(', ') if documentadas else "('', '')" }}) as t(modelo, coluna)
)
select f.* from fisicas f
left join doc d using (modelo, coluna)
where d.coluna is null
