import json
import logging
import os
import urllib3

# Configuração do logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Variáveis globais para cachear o cliente e a chave
API_KEY = None
HTTP = None
OPENAI_URL = "https://api.openai.com/v1/embeddings"

def _initialize():
    """Função de inicialização para ser chamada na primeira execução."""
    global API_KEY, HTTP
    if API_KEY is None:
        logger.info("Inicializando o cliente HTTP e a chave de API.")
        try:
            API_KEY = os.environ["OPENAI_API_KEY"]
            HTTP = urllib3.PoolManager(timeout=urllib3.Timeout(connect=2, read=25))
        except KeyError:
            logger.error("A variável de ambiente OPENAI_API_KEY não foi definida.")
            # Deixa API_KEY como None para indicar falha na inicialização
    return API_KEY is not None


def lambda_handler(event, context):
    """
    Função Lambda que atua como um proxy seguro para a API de Embeddings da OpenAI.
    """
    # Inicialização "lazy" na primeira invocação
    if not _initialize():
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Erro de configuração do servidor: a variável de ambiente OPENAI_API_KEY não foi definida."})
        }

    logger.info("Recebida requisição de proxy para a OpenAI.")

    try:
        request_body = event['body']
    except (KeyError, TypeError):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Corpo da requisição inválido ou ausente."})
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    try:
        # Repassa a requisição para a OpenAI
        response = HTTP.request(
            "POST",
            OPENAI_URL,
            body=request_body,
            headers=headers,
            timeout=25
        )

        response_body = response.data.decode("utf-8")
        logger.info(f"Resposta da OpenAI recebida com status: {response.status}")

        # Retorna a resposta da OpenAI (sucesso ou erro) para o chamador
        return {
            "statusCode": response.status,
            "body": response_body
        }

    except urllib3.exceptions.RequestError as e:
        logger.error(f"Erro de rede ao chamar a API da OpenAI: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Erro de comunicação com a OpenAI: {str(e)}"})
        }
    except Exception as e:
        logger.error(f"Erro inesperado no proxy: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Erro inesperado: {str(e)}"})
        }
