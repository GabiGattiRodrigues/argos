-- Finalidade "marketing": base legal é o consentimento. Quem não consentiu ou revogou
-- simplesmente não está aqui, e cliente encerrado também não.
select id_cliente, nome, email, telefone, cidade, uf, data_cadastro
from {{ ref('silver_clientes') }}
where consentimento_marketing_ativo
  and status_cliente = 'ativo'
