# Prompt para Desenvolvimento da Lambda `query_function` (Versão com Proxy)

> ### Persona
>
> Você é um engenheiro de software sênior especializado em arquiteturas serverless na AWS e no desenvolvimento de aplicações de IA.
>
> ### Contexto
>
> Estamos construindo o serviço **Cortexa**. Esta função, `query_function`, realiza a busca semântica.
>
> A arquitetura foi atualizada: as chamadas para a API da OpenAI agora são feitas através de uma **Lambda de proxy segura**.
>
> * **Proxy Lambda ARN:** `arn:aws:lambda:us-east-1:497568177086:function:openai-embedding-proxy` (exemplo)
> * **Banco de Dados:** Neon DB com `pg_vector`.
>
> ### Tarefa
>
> Escreva o código Python completo para a `query_function`. A função deve:
> 1.  Receber `knowledgeBaseId`, `query` e `top_k` via API Gateway.
> 2.  **Montar o payload** para a API de Embeddings da OpenAI (ex: `{"input": "texto da query", "model": "text-embedding-3-small"}`).
> 3.  **Invocar a Lambda de proxy** usando `boto3` para obter o vetor da query.
> 4.  Executar a busca vetorial no Neon DB usando o operador `<=>` do `pg_vector`.
> 5.  Retornar os `top_k` resultados mais relevantes.
>
> ### Requisitos e Boas Práticas
>
> 1.  **Segurança:** Use variáveis de ambiente para:
>     * `NEON_DB_CONNECTION_STRING`
>     * `OPENAI_PROXY_LAMBDA_ARN`
> 2.  **Dependências:** O código deve usar `psycopg2-binary` e `boto3`. **Não use a biblioteca `openai` aqui.**
> 3.  **Invocação da Lambda:** Use `boto3.client('lambda').invoke()` para chamar a função de proxy. Trate a resposta para extrair o vetor de embedding.
> 4.  **Otimização:** Mantenha a conexão com o DB e o cliente `boto3` fora do handler.
> 5.  **Robustez:** Implemente tratamento de erros completo.