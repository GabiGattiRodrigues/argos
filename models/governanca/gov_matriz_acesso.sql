-- A política (vars.papeis) em formato de tabela: papel x tipo de dado x tratamento.
{%- set linhas = [] -%}
{%- for papel, cfg in var('papeis').items() -%}
  {%- for tipo, t in var('tipos_dado').items() -%}
    {%- do linhas.append("('" ~ papel ~ "', '" ~ tipo ~ "', '" ~ t.classificacao ~ "', '" ~ cfg.politica.get(tipo, 'remover') ~ "')") -%}
  {%- endfor -%}
{%- endfor %}
select * from (values
    {{ linhas | join(',\n    ') }}
) as t(papel, tipo_dado, classificacao, tratamento)
