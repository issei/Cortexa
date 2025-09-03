# Prompt para Desenvolvimento de Testes Unitários e Integração com CI/CD

## Objetivo

Este documento fornece um prompt detalhado para ser usado por um assistente de IA (como o Jules.Google) para:
1.  Gerar o código dos testes unitários para todas as funções Lambda do projeto Cortexa (`ingest_function`, `query_function`, `openai-embedding-proxy`).
2.  Modificar o workflow do GitHub Actions (`deploy.yml`) para executar esses testes como uma etapa de validação obrigatória em cada Pull Request.

---

## O Prompt

> ### Persona
>
> Você é um Engenheiro de Qualidade de Software (SQA) sênior, com profunda experiência em automação de testes para aplicações serverless em Python. Sua especialidade é criar testes unitários eficazes que isolam a lógica de negócio de dependências externas através de mocking, e integrar esses testes em pipelines de CI/CD para garantir que apenas código de alta qualidade chegue à produção.
>
> ### Contexto
>
> Estamos trabalhando no projeto **Cortexa**. Já temos as funções Lambda e um pipeline de CI/CD para deploy. Agora, precisamos adicionar uma camada de testes unitários para validar a lógica de cada função de forma isolada, sem fazer chamadas reais a serviços externos (AWS, OpenAI, Neon DB).
>
> Usaremos o framework **`pytest`** e a biblioteca **`pytest-mock`** (que facilita o uso do `unittest.mock` da biblioteca padrão do Python).
>
> A estrutura de diretórios do projeto será atualizada para incluir os testes:
>
> ```
> .
> ├── .github/
> │   └── workflows/
> │       └── deploy.yml      <-- Arquivo a ser modificado
> ├── src/
> │   ├── ingest_function/
> │   │   └── main.py
> │   └── ... (outras funções)
> ├── tests/                  <-- Novo diretório
> │   ├── test_ingest_function.py
> │   ├── test_query_function.py
> │   └── test_openai_embedding_proxy.py
> ├── terraform/
> │   └── ...
> └── requirements-dev.txt    <-- Novo arquivo
> ```
>
> ### Tarefa 1: Gerar os Arquivos de Teste Unitário
>
> Para cada uma das três funções Lambda (`ingest_function`, `query_function`, e `openai-embedding-proxy`), gere um arquivo de teste Python correspondente.
>
> #### Requisitos Gerais de Teste:
>
> 1.  **Isolamento Total:** Os testes **NÃO DEVEM** fazer chamadas de rede reais. Todas as dependências externas devem ser "mockadas".
> 2.  **Mocking:**
>     * Use o `mocker` do `pytest-mock` para simular as respostas dos clientes `boto3` e `psycopg2`.
>     * Simule a leitura de variáveis de ambiente com `mocker.patch.dict(os.environ, {...})`.
>     * Simule a biblioteca `urllib3` no proxy para evitar chamadas reais à OpenAI.
> 3.  **Cobertura de Cenários:** Cada arquivo de teste deve cobrir:
>     * O "caminho feliz" (happy path) com inputs válidos.
>     * Casos de erro de input (ex: campos faltando no JSON).
>     * Casos de falha nas dependências (ex: o que acontece se o `boto3.invoke` falhar ou o DB retornar um erro).
>
> #### Cenários Específicos a Testar:
>
> * **`test_ingest_function.py`:**
>     * Deve testar se a função divide o texto corretamente em chunks com sobreposição.
>     * Deve verificar se a função invoca a Lambda de proxy (`boto3`) com o payload correto para cada chunk.
>     * Deve verificar se a função constrói e executa a query de `INSERT` em lote no banco de dados com os dados corretos.
>     * Deve testar o retorno de um erro 400 se `text` ou `knowledgeBaseId` estiverem ausentes.
>
> * **`test_query_function.py`:**
>     * Deve testar se a função invoca a Lambda de proxy com o payload correto para a query do usuário.
>     * Deve verificar se a query SQL de busca vetorial (`SELECT ... ORDER BY embedding <=> %s`) é construída corretamente.
>     * Deve testar o comportamento do `top_k` padrão quando ele não é fornecido.
>     * Deve simular uma resposta do banco de dados e verificar se a função a formata corretamente na saída JSON.
>
> * **`test_openai_embedding_proxy.py`:**
>     * Deve testar se a função lê a `OPENAI_API_KEY` do ambiente corretamente.
>     * Deve simular uma chamada bem-sucedida da `urllib3.request` e verificar se a resposta é repassada.
>     * Deve simular uma resposta de erro da `urllib3.request` (ex: status 401) e garantir que o erro é propagado.
>     * Deve testar o caso em que a `OPENAI_API_KEY` não está definida no ambiente.
>
> ### Tarefa 2: Integrar os Testes no Workflow de CI/CD
>
> Modifique o arquivo `.github/workflows/deploy.yml` para incluir a execução dos testes.
>
> #### Requisitos de Modificação do Workflow:
>
> 1.  **Criação de `requirements-dev.txt`:** Crie um arquivo `requirements-dev.txt` na raiz do projeto contendo:
>     ```
>     pytest
>     pytest-mock
>     boto3
>     ```
> 2.  **Atualização do Job `validate_terraform`:** No job que é acionado em **Pull Requests**, adicione os seguintes passos **antes** dos passos do Terraform:
>     * **Instalar Python:** Use a action `actions/setup-python@v4`.
>     * **Instalar Dependências de Teste:** Execute `pip install -r requirements-dev.txt`.
>     * **Executar Testes:** Execute o comando `pytest tests/`.
> 3.  **Validação:** O workflow deve falhar se qualquer um dos testes falhar, bloqueando o merge do Pull Request.
>
> ### Output Esperado
>
> 1.  Três arquivos de código Python: `test_ingest_function.py`, `test_query_function.py`, e `test_openai_embedding_proxy.py`.
> 2.  Um arquivo de texto: `requirements-dev.txt`.
> 3.  A versão atualizada e completa do arquivo `deploy.yml`, agora incluindo os passos para execução dos testes.