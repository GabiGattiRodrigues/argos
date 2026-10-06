-- Bronze: cópia fiel da origem. O contrato (no YAML) barra mudança de nome ou tipo de coluna.
select * from {{ source('origem', 'cartoes') }}
