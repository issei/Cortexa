# Documentação: Integração do Neon com o CI/CD do Cortexa

**Versão:** 1.0
**Data:** 3 de Setembro de 2025
**Autor:** Jules.Google

## Sumário

1.  [Visão Geral e Filosofia](#1-visão-geral-e-filosofia-database-branching)
2.  [O Workflow de CI/CD para Pull Requests](#2-o-workflow-de-cicd-para-pull-requests)
    * [Gatilhos do Workflow](#a-gatilhos-do-workflow)
    * [Fase 1: Abertura ou Atualização de um Pull Request](#b-fase-1-abertura-ou-atualização-de-um-pull-request)
    * [Fase 2: Fechamento de um Pull Request](#c-fase-2-fechamento-de-um-pull-request)
3.  [Requisitos de Configuração](#3-requisitos-de-configuração)
    * [Estrutura de Diretórios](#estrutura-de-diretórios)
    * [Segredos e Variáveis do GitHub](#segredos-e-variáveis-do-github)
4.  [Vantagens para o Projeto Cortexa](#4-vantagens-para-o-projeto-cortexa)

---

## 1. Visão Geral e Filosofia: Database Branching

Para garantir agilidade e segurança no desenvolvimento do Cortexa, adotamos uma estratégia moderna de CI/CD para nosso banco de dados, possibilitada pela funcionalidade de **Database Branching** da Neon.

**O Problema Tradicional:** Em ambientes de desenvolvimento convencionais, equipes geralmente compartilham um único banco de dados de `staging` ou `dev`. Isso leva a problemas como:
* Dados de teste de um desenvolvedor interferindo com os de outro.
* Conflitos de schema quando diferentes features estão em desenvolvimento.
* Medo de aplicar uma migração de banco de dados que possa quebrar o ambiente para toda a equipe.

**A Solução com Neon:** A cada Pull Request (PR) aberto no repositório do Cortexa, nosso pipeline de CI/CD cria automaticamente uma **ramificação (branch) do banco de dados principal**. Essa ramificação é um clone instantâneo, isolado e totalmente funcional do nosso banco de dados, mas que pode ser modificado e testado sem qualquer impacto no ambiente principal ou em outras ramificações.

Essa abordagem nos permite tratar a infraestrutura do banco de dados da mesma forma que tratamos o código: com branches, testes automatizados e revisões, tudo de forma descartável e sob demanda.

## 2. O Workflow de CI/CD para Pull Requests

Utilizamos um workflow do GitHub Actions, definido no arquivo `.github/workflows/neon_workflow.yml`, para orquestrar todo esse processo.

### a) Gatilhos do Workflow

O pipeline é acionado automaticamente pelos seguintes eventos em um Pull Request direcionado à branch `main`:
* `opened`: Quando um novo PR é criado.
* `reopened`: Quando um PR fechado é reaberto.
* `synchronize`: Quando novos commits são adicionados a um PR existente.
* `closed`: Quando um PR é fechado (seja por merge ou descarte).

### b) Fase 1: Abertura ou Atualização de um Pull Request

Quando um PR é aberto ou atualizado, o job `test_pr_branch` executa as seguintes etapas críticas:

1.  **Criação do Branch do Banco de Dados:**
    * A action oficial `neondatabase/create-branch-action` se conecta à API da Neon.
    * Ela cria um novo branch com um nome único ligado ao PR (ex: `preview/pr-42-feature-nova-api`).
    * A action expõe a string de conexão segura para este banco de dados temporário, que será usada nos passos seguintes.

2.  **Aplicação de Migrações de Schema:**
    * O workflow verifica o diretório `database/migrations/` em busca de novos scripts `.sql`.
    * Usando o cliente `psql`, ele aplica esses scripts **no banco de dados temporário recém-criado**. Isso garante que as novas tabelas, colunas ou índices propostos no PR sejam criados e validados.

3.  **Execução de Testes Unitários:**
    * O ambiente Python é configurado, e as dependências de teste (pytest, etc.) são instaladas a partir de `requirements-dev.txt`.
    * A suíte de testes unitários, localizada em `tests/`, é executada. Isso valida a lógica de negócio das funções Lambda (`ingest`, `query`, etc.) contra as últimas alterações de código.

4.  **Análise de Diferenças de Schema (Opcional, mas recomendado):**
    * A action `neondatabase/schema-diff-action` compara o schema do branch temporário (com as novas migrações) com o do branch principal.
    * Ela posta um comentário automático no Pull Request, mostrando um resumo claro das mudanças no banco de dados (ex: `+ Tabela 'users' criada`, `+ Coluna 'email' adicionada a 'profiles'`). Isso enriquece enormemente o processo de code review.

Se qualquer uma dessas etapas falhar (seja uma migração com erro de sintaxe ou um teste quebrado), o workflow do GitHub Actions falhará, e um X vermelho aparecerá no Pull Request, sinalizando que as mudanças não estão prontas para serem integradas.

### c) Fase 2: Fechamento de um Pull Request

Quando um PR é finalmente fechado (seja integrado à `main` ou descartado), o job `delete_neon_branch` é acionado:

1.  **Limpeza Automática:**
    * A action `neondatabase/delete-branch-action` se conecta à API da Neon.
    * Ela localiza o branch do banco de dados associado ao PR fechado e o **exclui permanentemente**.
    * Isso garante que nosso projeto na Neon permaneça limpo, contendo apenas os branches ativos e relevantes, e que não haja custos residuais de computação para bancos de dados de PRs antigos.

## 3. Requisitos de Configuração

Para que essa integração funcione, a seguinte configuração é necessária no repositório do GitHub (`issei/Cortexa`):

#### Estrutura de Diretórios
```

.
├── .github/
│   └── workflows/
│       └── neon\_workflow.yml  \<-- O workflow de CI/CD
├── database/
│   └── migrations/
│       └── V1\_\_create\_initial\_tables.sql  \<-- Scripts de mudança de schema
├── tests/
│   └── test\_ingest\_function.py  \<-- Testes unitários
└── requirements-dev.txt  \<-- Dependências de teste (pytest, etc.)

```

#### Segredos e Variáveis do GitHub
Navegue até `Settings` > `Secrets and variables` > `Actions`:

* **Secrets:**
    * `NEON_API_KEY`: Essencial para permitir que o GitHub Actions se autentique na API da Neon e gerencie os branches.
* **Variables:**
    * `NEON_PROJECT_ID`: Identifica qual projeto na sua conta Neon o workflow deve gerenciar.

## 4. Vantagens para o Projeto Cortexa

Adoção desta estratégia de CI/CD com Neon traz benefícios imensos para o desenvolvimento do Cortexa:

* **Desenvolvimento Paralelo e Seguro:** Múltiplos desenvolvedores podem trabalhar em features que alteram o banco de dados simultaneamente, cada um em seu próprio PR com seu próprio banco de dados isolado.
* **Confiança nas Mudanças:** Cada PR é rigorosamente validado. Sabemos que, se o pipeline passar, as mudanças no código são testadas e as migrações de banco de dados são aplicáveis.
* **Revisões de PR de Alta Qualidade:** Os revisores podem analisar não apenas o código, mas também o resultado dos testes e o relatório de impacto no schema do banco, tudo dentro da interface do Pull Request.
* **Custo-Eficiência:** A natureza serverless do Neon significa que esses branches temporários não têm custo de armazenamento fixo e só consomem recursos de computação durante os poucos minutos em que o pipeline de CI está em execução.