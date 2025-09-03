# Prompt para Geração da Lambda `openai-embedding-proxy`

## Objetivo

Este documento fornece um prompt detalhado e otimizado para ser usado por um assistente de IA (como o Jules.Google) para gerar o código Python da função Lambda `openai-embedding-proxy`. O objetivo é obter um código seguro, eficiente e reutilizável que sirva como um proxy para o serviço de embeddings da OpenAI, centralizando a gestão da chave de API.

---

## O Prompt

> ### Persona
>
> Você é um engenheiro de software sênior com foco em segurança, otimização de custos e melhores práticas em arquiteturas serverless na AWS. Seu código deve ser minimalista, robusto e seguro.
>
> ### Contexto
>
> Estamos construindo um serviço chamado **Cortexa**. Esta função Lambda, `openai-embedding-proxy`, não contém lógica de negócio principal. Sua única responsabilidade é atuar como um **proxy seguro e centralizado** para a API de Embeddings da OpenAI.
>
> O principal objetivo desta função é **evitar que a chave da API da OpenAI (`OPENAI_API_KEY`) seja distribuída** em múltiplas funções Lambda (`ingest_function`, `query_function`, etc.). Em vez disso, outras Lambdas dentro da nossa conta AWS invocarão esta função para obter embeddings, e apenas ela terá acesso à chave secreta.
>
> ### Tarefa
>
> Escreva o código Python completo para a função Lambda `openai-embedding-proxy`.
>
> A função deve:
> 1.  Ser invocada por outras funções Lambda (não pela API Gateway). O evento de entrada conterá um `body` que é uma string JSON.
> 2.  Ler a chave da API da OpenAI a partir de suas próprias variáveis de ambiente.
> 3.  Repassar o `body` recebido **diretamente e sem modificações** para o endpoint `https://api.openai.com/v1/embeddings`.
> 4.  Aguardar a resposta da OpenAI.
> 5.  Retornar a resposta completa da OpenAI (tanto em caso de sucesso quanto de erro) de volta para a função que a invocou.
>
> ### Requisitos e Boas Práticas
>
> 1.  **Segurança Máxima:** A `OPENAI_API_KEY` **DEVE** ser lida a partir de uma variável de ambiente (`os.environ.get('OPENAI_API_KEY')`). A função deve retornar um erro 500 se a chave não estiver configurada.
> 2.  **Mínimas Dependências:** Para manter o pacote de deploy pequeno e o cold start rápido, não use bibliotecas de terceiros pesadas como `requests`. Utilize a biblioteca padrão `urllib3`, que já vem com o runtime da AWS Lambda.
> 3.  **Eficiência:** O cliente HTTP (ex: `urllib3.PoolManager`) e a leitura da variável de ambiente devem ser feitos **fora do handler principal** para serem reutilizados em invocações "quentes" (warm invocations).
> 4.  **Lógica de Proxy "Pass-Through":** A função deve ser genérica. Ela não deve tentar analisar ou validar o conteúdo do `body`, apenas repassá-lo. Isso a torna mais resiliente a futuras mudanças na API da OpenAI.
> 5.  **Tratamento de Erros Robusto:**
>     * Implemente um `timeout` na requisição para a OpenAI (ex: 25 segundos) para evitar que a função execute por tempo demais.
>     * Capture exceções de rede e timeouts.
>     * Se a API da OpenAI retornar um status de erro (ex: 401, 429, 500), a função deve propagar esse mesmo status e corpo de erro para o chamador.
> 6.  **Logging:** Inclua logs concisos para depuração em CloudWatch, como "Recebida requisição de proxy" ou "Erro retornado pela OpenAI com status X".
> 7.  **Formato de Retorno:** A função deve retornar um dicionário Python contendo `statusCode` e `body` (como uma string JSON), para que a função chamadora possa facilmente interpretar o resultado.
>
> ### Exemplo de Interação
>
> * **Input (Payload da função que a invoca):**
>
> ```python
> # Exemplo de como a ingest_function chamaria esta Lambda
> invoke_payload = {
>     "body": json.dumps({
>         "input": "Este é um texto para gerar embedding.",
>         "model": "text-embedding-3-small"
>     })
> }
> ```
>
> * **Output (Retorno da função proxy em caso de sucesso):**
>
> ```json
> {
>   "statusCode": 200,
>   "body": "{\"object\":\"list\",\"data\":[{\"object\":\"embedding\",\"index\":0,\"embedding\":[...vetor...]}],\"model\":\"text-embedding-3-small-v1\",\"usage\":{...}}"
> }
> ```
>
> * **Output (Retorno da função proxy em caso de erro da OpenAI):**
>
> ```json
> {
>   "statusCode": 401,
>   "body": "{\"error\": {\"message\": \"Incorrect API key provided...\", ...}}"
> }
> ```

---
