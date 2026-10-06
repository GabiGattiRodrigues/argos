select
    id_cliente, nome, cpf, email, telefone, data_nascimento, renda_mensal, endereco, cep,
    cidade, uf, ocupacao, pep, status_cliente, data_cadastro, data_encerramento,
    consentimento_marketing_ativo
from {{ ref('silver_clientes') }}
