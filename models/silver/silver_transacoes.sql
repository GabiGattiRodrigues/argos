with origem as (select * from {{ ref('bronze_transacoes') }}),
     mcc as (select * from {{ ref('mcc') }})

select
    t.id_transacao,
    t.id_cartao,
    t.data_hora,
    cast(t.data_hora as date)  as data,
    round(t.valor, 2)          as valor,
    t.mcc,
    coalesce(mcc.categoria, 'Outros')        as categoria_mcc,
    coalesce(mcc.alto_risco_pld, false)      as mcc_alto_risco_pld,
    t.estabelecimento,
    t.canal,
    t.status                   as status_transacao
from origem t
left join mcc on mcc.mcc = t.mcc
