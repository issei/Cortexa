import os
import json
import urllib3
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Otimização: Inicialize o cliente e a chave fora do handler
http = urllib3.PoolManager(
    timeout=urllib3.Timeout(connect=2.0, read=25.0),
    retries=urllib3.Retry(
        total=3,  # número total de tentativas
        backoff_factor=0.5,  # tempo entre tentativas: {0.5, 1, 2} segundos
        status_forcelist=[500, 502, 503, 504]  # status que devem ser retentados
    )
)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_URL = "https://api.openai.com/v1/embeddings"

def handler(event, context):
    """
    Atua como um proxy seguro para a API de Embeddings da OpenAI.
    Recebe um corpo de requisição e o repassa diretamente para a OpenAI.

    Args:
        event (dict): Evento Lambda contendo o body da requisição
        context (LambdaContext): Contexto de execução da Lambda

    Returns:
        dict: Resposta contendo statusCode e body
    """
    request_id = context.aws_request_id
    logger.info(f"Iniciando processamento da requisição {request_id}")

    # Validação da configuração
    if not OPENAI_API_KEY:
        logger.error(f"[{request_id}] OPENAI_API_KEY não configurada")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server configuration error",
                "request_id": request_id
            })
        }

    try:
        # Validação do corpo da requisição
        request_body = event.get('body')
        if not request_body:
            logger.warning(f"[{request_id}] Requisição recebida sem body")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Request body is missing",
                    "request_id": request_id
                })
            }

        # Validação do formato JSON do body
        try:
            json.loads(request_body)
        except json.JSONDecodeError:
            logger.warning(f"[{request_id}] Body da requisição não é um JSON válido")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Request body must be a valid JSON string",
                    "request_id": request_id
                })
            }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {OPENAI_API_KEY}'
        }

        logger.info(f"[{request_id}] Iniciando chamada à API da OpenAI")
        
        # Realiza a chamada para a API da OpenAI
        response = http.request(
            'POST',
            OPENAI_URL,
            body=request_body,
            headers=headers
        )

        response_data = json.loads(response.data.decode('utf-8'))

        # Se a OpenAI retornar um erro, propague-o
        if response.status >= 400:
            logger.error(f"[{request_id}] Erro da OpenAI: Status {response.status}")
            return {
                "statusCode": response.status,
                "body": json.dumps({
                    **response_data,
                    "request_id": request_id
                })
            }

        logger.info(f"[{request_id}] Requisição processada com sucesso")
        
        # Retorna a resposta de sucesso da OpenAI
        return {
            "statusCode": 200,
            "body": json.dumps({
                **response_data,
                "request_id": request_id
            })
        }

    except urllib3.exceptions.TimeoutError:
        logger.error(f"[{request_id}] Timeout na chamada à API da OpenAI")
        return {
            "statusCode": 504,
            "body": json.dumps({
                "error": "Request to OpenAI API timed out",
                "request_id": request_id
            })
        }
    except urllib3.exceptions.HTTPError as e:
        logger.error(f"[{request_id}] Erro de rede na chamada à API da OpenAI: {str(e)}")
        return {
            "statusCode": 502,
            "body": json.dumps({
                "error": "Network error while calling OpenAI API",
                "request_id": request_id,
                "details": str(e)
            })
        }
    except Exception as e:
        logger.error(f"[{request_id}] Erro inesperado: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "An internal error occurred while proxying the request",
                "request_id": request_id
            })
        }