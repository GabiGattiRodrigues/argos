# Argos · governança de dados sensíveis

> Todo mundo na empresa precisa de dado de cliente. Quase ninguém precisa saber **quem** é o cliente.

O Argos transforma essa frase em código, num cenário de fintech de cartão (dados 100% sintéticos):

- **Classificação** — cada coluna de consumo declara o tipo de dado que carrega (`cpf`, `renda`, `cep`…). O tipo herda uma classificação (restrito, confidencial, interno) de um catálogo único.
- **Política como código** — uma matriz no `dbt_project.yml` diz, para cada papel, o tratamento de cada tipo: em claro, pseudonimizar, mascarar, generalizar em faixa ou remover. Tipo sem regra é removido (falha fechada).
- **Views geradas, não escritas** — a macro `aplicar_politica` lê o grafo do dbt e gera a view de cada papel. Coluna sem classificação quebra o build.
- **Conferência da saída** — um teste varre o dado servido procurando CPF, telefone e e-mail. Não confia na política, confere o resultado.
- **Contratos de dados** — esquema das fontes travado por contrato do dbt; regras de qualidade do contrato (`contratos/transacoes.yml`) viram testes. O CI simula três incidentes a cada build e falha se algum passar.
- **Finalidade, minimização e retenção** — base de marketing só com consentimento vigente; número do cartão não passa do bronze; fila de anonimização por prazo de retenção parametrizado.

Página do projeto: https://gabigattirodrigues.github.io/argos/ · Documentação e linhagem: https://gabigattirodrigues.github.io/argos/docs/

## Papéis

| Papel | Para quê | Vê |
|---|---|---|
| `analista_bi` | dashboards e indicadores | cliente pseudonimizado; idade, renda e CEP em faixa |
| `cientista_dados` | modelos de risco e propensão | pseudônimo + renda exata, PEP; sem contato nem identidade |
| `compliance_pld` | monitoramento de PLD e COAF | identidade completa; e-mail e telefone mascarados |
| `crm_marketing` | campanhas | contato em claro, **só** de quem consentiu |

Cada papel consome um schema `acesso_<papel>`; bronze e silver não são concedidos a ninguém.

## Camadas

```
data/raw/*.csv ──► bronze (cópia fiel + contrato) ──► silver (limpeza, minimização) ──► gold (contratos, classificação)
                                                                                      ├─► acesso_<papel> (views geradas pela política)
                                                                                      └─► governanca (catálogo, matriz, fila de retenção)
```

## Rodar localmente

```bash
pip install -r requirements.txt
python scripts/gerar_dados.py          # 5 mil clientes, ~6,5 mil cartões, ~150 mil transações
dbt build --profiles-dir .             # modelos, contratos e testes
python scripts/simular_incidentes.py   # 3 incidentes: todos devem ser barrados
python scripts/gerar_pagina.py         # site/index.html
```

No Windows, o jeito mais fácil é dar dois cliques no `rodar.bat` (cria o ambiente, instala tudo e abre um menu). Rodando à mão, defina antes `set PYTHONUTF8=1`: o dbt lê os YAML com a codificação padrão do sistema, que no Windows não é UTF-8.

O banco fica em `argos.duckdb` (mude com a variável `ARGOS_DB`). O segredo da pseudonimização vem de `ARGOS_SEGREDO`; sem ela, usa um valor de desenvolvimento.

## Incidentes simulados

| Incidente | O que muda | Onde para |
|---|---|---|
| Quebra de esquema | `valor` vira `valor_transacao` | contrato do `bronze_transacoes` |
| Troca silenciosa de unidade | `valor` passa a vir em centavos, mesmo nome e tipo | teste de ticket médio diário do contrato |
| Coluna sem classificação | coluna da gold perde o `tipo_dado` | geração das views de acesso |

## Avisos

Todos os dados são sintéticos (Faker + numpy, semente fixa). CPFs têm dígito verificador válido só para testar as regras; cartões usam prefixo de teste. As referências à LGPD e a normas do Banco Central ilustram o desenho e não são parecer jurídico.

Projeto de portfólio de [Gabriela Gatti Rodrigues](https://gabigattirodrigues.github.io/). Complementa o [Alexandria](https://gabigattirodrigues.github.io/alexandria/), que trata de modelagem e qualidade.
