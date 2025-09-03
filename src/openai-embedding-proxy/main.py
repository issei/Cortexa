import os
import json
import urllib3

# Otimização: Inicialize o cliente e a chave fora do handler
http = urllib3.PoolManager()
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_URL = "https://api.openai.com/v1/embeddings"

def handler(event, context):
    """
    Atua como um proxy seguro para a API de Embeddings da OpenAI.
    Recebe um corpo de requisição e o repassa diretamente para a OpenAI.
    """
    if not OPENAI_API_KEY:
        print("Erro: A variável de ambiente OPENAI_API_KEY não foi definida.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server configuration error."})
        }

    try:
        # Repassa o corpo do evento recebido diretamente para a OpenAI
        # A função que invoca esta deve garantir que o corpo está no formato correto
        request_body = event.get('body')
        if not request_body:
             return {"statusCode": 400, "body": json.dumps({"error": "Request body is missing."})}

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {OPENAI_API_KEY}'
        }

        # Realiza a chamada para a API da OpenAI
        response = http.request(
            'POST',
            OPENAI_URL,
            body=request_body,
            headers=headers,
            timeout=25.0 # Timeout de 25 segundos
        )

        response_data = json.loads(response.data.decode('utf-8'))

        # Se a OpenAI retornar um erro, propague-o
        if response.status >= 400:
             print(f"Erro da OpenAI: {response_data}")
             return {
                 "statusCode": response.status,
                 "body": json.dumps(response_data)
             }

        # Retorna a resposta de sucesso da OpenAI
        return {
            "statusCode": 200,
            "body": json.dumps(response_data)
        }

    except Exception as e:
        print(f"Erro inesperado: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "An internal error occurred while proxying the request."})
        }