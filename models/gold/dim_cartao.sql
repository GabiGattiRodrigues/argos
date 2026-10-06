select id_cartao, id_cliente, cartao_final, bandeira, produto, limite, data_emissao, status_cartao
from {{ ref('silver_cartoes') }}
