-- Silver: limpa e padroniza uma vez só. CPF, telefone e CEP passam a ter só dígitos.
with origem as (select * from {{ ref('bronze_clientes') }})

select
    id_cliente,
    trim(nome_completo)                                             as nome,
    regexp_replace(cpf, '[^0-9]', '', 'g')                          as cpf,
    lower(trim(email))                                              as email,
    -- tira o +55 e qualquer pontuação: fica DDD + número
    regexp_replace(regexp_replace(telefone, '^\s*\+55', ''), '[^0-9]', '', 'g') as telefone,
    data_nascimento,
    round(renda_mensal, 2)                                          as renda_mensal,
    trim(endereco)                                                  as endereco,
    lpad(regexp_replace(cep, '[^0-9]', '', 'g'), 8, '0')            as cep,
    cidade,
    upper(uf)                                                       as uf,
    ocupacao,
    pep,
    consentimento_marketing and data_revogacao_consentimento is null as consentimento_marketing_ativo,
    data_revogacao_consentimento,
    data_cadastro,
    data_encerramento,
    case when data_encerramento is null then 'ativo' else 'encerrado' end as status_cliente
from origem
