-- Catálogo de dados pessoais gerado a partir do próprio projeto (base para o registro das
-- operações de tratamento, LGPD art. 37). Se alguém adiciona uma coluna, ela aparece aqui.
{%- set linhas = [] -%}
{%- if execute -%}
  {%- set tipos = var('tipos_dado') -%}
  {%- for node in graph.nodes.values() | selectattr('resource_type', 'equalto', 'model') | sort(attribute='name') -%}
    {%- if node.fqn[1] == 'gold' -%}
      {%- set mm = node.config.get('meta', {}) -%}
      {%- for nome_col, col in node.columns.items() -%}
        {%- set tipo = meta_coluna(col).get('tipo_dado') -%}
        {%- set t = tipos.get(tipo, {}) -%}
        {%- do linhas.append("('" ~ node.name ~ "', '" ~ nome_col ~ "', " ~ ("'" ~ tipo ~ "'" if tipo else "null") ~ ", "
              ~ ("'" ~ t.classificacao ~ "'" if t else "null") ~ ", " ~ (t.dado_pessoal | string | lower if t else "null") ~ ", "
              ~ ("'" ~ t.nota ~ "'" if t else "null") ~ ", '" ~ mm.get('finalidade', '') ~ "', '" ~ mm.get('base_legal', '') ~ "', '"
              ~ mm.get('dono', '') ~ "', '" ~ (col.description | replace("'", "''")) ~ "')") -%}
      {%- endfor -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif %}
select * from (values
    {{ linhas | join(',\n    ') if linhas else "('', '', null, null, null, null, '', '', '', '')" }}
) as t(modelo, coluna, tipo_dado, classificacao, dado_pessoal, nota, finalidade, base_legal, dono, descricao)
{{ "where false" if not linhas }}
