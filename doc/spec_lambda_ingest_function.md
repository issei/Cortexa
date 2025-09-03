# Prompt para Desenvolvimento da Lambda `ingest_function` (Versão com Proxy)

> ### Persona
>
> Você é um engenheiro de software sênior especializado em arquiteturas serverless na AWS e no desenvolvimento de aplicações de IA.
>
> ### Contexto
>
> Estamos construindo o serviço **Cortexa**. Esta função, `ingest_function`, ingere e vetoriza textos.
>
> A arquitetura foi atualizada: as chamadas para a API da OpenAI agora são feitas através de uma **Lambda de proxy segura**.
>
> * **Proxy Lambda ARN:** `arn:aws:lambda:us-east-1:497568177086:function:openai-embedding-proxy` (exemplo)
> * **Banco de Dados:** Neon DB com `pg_vector`.
> * **Modelo de Dados:**
>
> ```sql
> CREATE TABLE knowledge_chunks (
>     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>     knowledge_base_id UUID NOT NULL,
>     content TEXT NOT NULL,
>     embedding VECTOR(1536) NOT NULL,
>     metadata JSONB,
>     created_at TIMESTAMPTZ DEFAULT NOW()
> );
> ```
>
> ### Tarefa
>
> Escreva o código Python completo para a `ingest_function`. A função deve:
> 1.  Receber `knowledgeBaseId` e `text` via API Gateway.
> 2.  Dividir o `text` em chunks.
> 3.  Para cada chunk:
>     a. **Montar o payload** para a API de Embeddings da OpenAI (ex: `{"input": "texto do chunk", "model": "text-embedding-3-small"}`).
>     b. **Invocar a Lambda de proxy** usando `boto3`, passando o payload.
>     c. Extrair o vetor de embedding da resposta da Lambda de proxy.
>     d. Inserir o chunk e o vetor no Neon DB.
> 4.  Retornar uma resposta de sucesso ou erro.
>
> ### Requisitos e Boas Práticas
>
> 1.  **Segurança:** Use variáveis de ambiente para:
>     * `NEON_DB_CONNECTION_STRING`
>     * `OPENAI_PROXY_LAMBDA_ARN`
> 2.  **Dependências:** O código deve usar `psycopg2-binary` e `boto3`. **Não use a biblioteca `openai` aqui.**
> 3.  **Invocação da Lambda:** Use `boto3.client('lambda').invoke()` para chamar a função de proxy. O payload deve ser um `json.dumps()` do corpo da requisição para a OpenAI. Lembre-se de decodificar a resposta.
> 4.  **Otimização:** Mantenha a conexão com o DB e o cliente `boto3` fora do handler para reutilização.
> 5.  **Robustez:** Trate erros tanto na invocação da Lambda de proxy quanto nas operações com o banco de dados.