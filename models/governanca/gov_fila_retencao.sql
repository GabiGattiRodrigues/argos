-- Fila de retenção: o que já passou do prazo e precisa ser tratado.
-- Cadastro de cliente encerrado: guardado pelo prazo de PLD após o fim do relacionamento,
-- depois anonimizado. Prazo parametrizado em vars.retencao_anos_pos_encerramento.
with ref as (select date '{{ var("data_referencia") }}' as hoje)

select
    id_cliente,
    'cadastro de cliente encerrado' as registro,
    data_encerramento               as data_gatilho,
    data_encerramento + interval {{ var('retencao_anos_pos_encerramento') }} year as prazo_ate,
    'anonimizar'                    as acao
from {{ ref('silver_clientes') }}, ref
where data_encerramento + interval {{ var('retencao_anos_pos_encerramento') }} year < hoje

union all

-- Consentimento revogado: o contato sai da base de marketing na hora (o mart já filtra);
-- aqui fica o registro para auditoria de que a revogação foi respeitada.
select
    id_cliente,
    'consentimento de marketing revogado',
    data_revogacao_consentimento,
    data_revogacao_consentimento,
    'excluir da base de marketing'
from {{ ref('silver_clientes') }}
where data_revogacao_consentimento is not null
