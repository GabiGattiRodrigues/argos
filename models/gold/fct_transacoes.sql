select
    t.id_transacao, t.id_cartao, c.id_cliente, t.data_hora, t.data, t.valor, t.mcc,
    t.categoria_mcc, t.mcc_alto_risco_pld, t.canal, t.status_transacao
from {{ ref('silver_transacoes') }} t
join {{ ref('silver_cartoes') }} c using (id_cartao)
