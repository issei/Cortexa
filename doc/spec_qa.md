# Especificação de Testes e CI/CD do Projeto Cortexa

## Objetivo

Este documento especifica a estrutura e requisitos dos testes automatizados do projeto Cortexa, abrangendo:

1. Testes unitários para todas as funções Lambda (`ingest_function`, `query_function`, `openai-embedding-proxy`)
2. Testes de integração para validar a interação entre os componentes
3. Pipeline de CI/CD com validação automática em Pull Requests

## Estrutura do Projeto

```
.
├── .github/
│   └── workflows/
│       ├── ci.yml         # Workflow de PR: lint, test, plan
│       └── cd.yml         # Workflow de deploy: apply, deploy
├── src/
│   ├── ingest_function/
│   │   └── main.py
│   ├── query_function/
│   │   └── main.py
│   └── openai_embedding_proxy/
│       └── main.py
├── tests/
│   ├── conftest.py                     # Fixtures compartilhadas
│   ├── test_ingest_function.py
│   ├── test_query_function.py
│   └── test_openai_embedding_proxy.py
├── terraform/
│   └── ...
└── requirements-dev.txt                 # Dependências de desenvolvimento
```

## Dependências de Desenvolvimento

O arquivo `requirements-dev.txt` define as dependências necessárias para desenvolvimento e teste:

```
# Framework de testes
pytest>=7.4.0
pytest-mock>=3.11.1
pytest-cov>=4.1.0

# SDKs e clientes
boto3>=1.28.0
psycopg2-binary>=2.9.9
urllib3>=2.0.0

# Linting e formatação
black>=23.7.0
pylint>=2.17.5
```

## Fixtures Compartilhadas (conftest.py)

Fixtures comuns a todos os testes, incluindo:

1. **Mock de Ambiente**:
   - Variáveis de ambiente (DB, OpenAI)
   - Clientes AWS
   - Conexões de banco

2. **Mock de Respostas**:
   - Respostas da OpenAI
   - Resultados do banco
   - Payloads padrão

3. **Utilitários**:
   - Reset de estado global
   - Geração de dados de teste
   - Helpers de asserção

## Especificação dos Testes Unitários

### Requisitos Gerais

1. **Isolamento e Mocking**:
   - Zero chamadas de rede reais nos testes unitários
   - Mock de todas as dependências externas (boto3, psycopg2, urllib3)
   - Simulação de variáveis de ambiente
   - Controle de estado global entre testes

2. **Organização dos Testes**:
   - Agrupamento por funcionalidade
   - Uso de fixtures para reutilização
   - Parametrização para múltiplos cenários
   - Marcadores para categorização (@pytest.mark.integration, @pytest.mark.performance)

3. **Cobertura de Código**:
   - Mínimo de 90% de cobertura
   - Todos os caminhos de erro testados
   - Validação de edge cases
   - Testes de performance e carga

### Testes por Componente

#### 1. Ingest Function (`test_ingest_function.py`)

1. **Testes de Chunking**:
   ```python
   @pytest.mark.parametrize("test_input,chunk_size,chunk_overlap,expected", [
       ("texto simples", 20, 5, ["texto simples"]),
       ("texto longo para dividir", 10, 2, ["texto longo", "ngo para", "a dividir"]),
       ("", 20, 5, []),  # texto vazio
       (None, 20, 5, [])  # input inválido
   ])
   ```

2. **Testes de Embedding**:
   - Geração correta para cada chunk
   - Tratamento de erros do proxy
   - Validação de limites de tamanho

3. **Testes de Banco**:
   - Inserção em lote correta
   - Rollback em caso de erro
   - Reutilização de conexões

#### 2. Query Function (`test_query_function.py`)

1. **Testes de Parâmetros**:
   - Validação de top_k
   - Tratamento de knowledgeBaseId
   - Sanitização de input

2. **Testes de Busca**:
   - Ordenação por similaridade
   - Formatação de resultados
   - Metadados e scores

3. **Testes de Performance**:
   - Caching de conexões
   - Comportamento com grande volume
   - Timeouts e retries

#### 3. OpenAI Proxy (`test_openai_embedding_proxy.py`)

1. **Testes de Inicialização**:
   - Validação de API key
   - Configuração de timeout
   - Reutilização de clientes

2. **Testes de Chamadas**:
   - Sucesso da requisição
   - Diferentes códigos de erro
   - Timeout e retry

3. **Testes de Formato**:
   - Validação de input
   - Tamanho dos vetores
   - Headers e autenticação

### Tarefa 2: Integrar os Testes no Workflow de CI/CD

Modifique o arquivo `.github/workflows/deploy.yml` para incluir a execução dos testes.

#### Requisitos de Modificação do Workflow:

1.  **Criação de `requirements-dev.txt`:** Crie um arquivo `requirements-dev.txt` na raiz do projeto contendo:
    ```
    pytest
    pytest-mock
    boto3
    ```
2.  **Atualização do Job `validate_terraform`:** No job que é acionado em **Pull Requests**, adicione os seguintes passos **antes** dos passos do Terraform:
    * **Instalar Python:** Use a action `actions/setup-python@v4`.
    * **Instalar Dependências de Teste:** Execute `pip install -r requirements-dev.txt`.
    * **Executar Testes:** Execute o comando `pytest tests/`.
3.  **Validação:** O workflow deve falhar se qualquer um dos testes falhar, bloqueando o merge do Pull Request.

### Output Esperado

1.  Três arquivos de código Python: `test_ingest_function.py`, `test_query_function.py`, e `test_openai_embedding_proxy.py`.
2.  Um arquivo de texto: `requirements-dev.txt`.
3.  A versão atualizada e completa do arquivo `deploy.yml`, agora incluindo os passos para execução dos testes.
