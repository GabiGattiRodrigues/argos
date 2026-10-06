-- Silver: minimização de dados. O número completo do cartão não passa daqui:
-- ficam só o BIN (6 primeiros), os 4 últimos e um token para conciliação.
with origem as (select * from {{ ref('bronze_cartoes') }})

select
    id_cartao,
    id_cliente,
    {{ pseudonimizar('numero_cartao') }}  as token_cartao,
    left(numero_cartao, 6)                as bin,
    right(numero_cartao, 4)               as cartao_final,
    bandeira,
    produto,
    limite,
    data_emissao,
    status                                as status_cartao
from origem
