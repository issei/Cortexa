import json
import logging
import os
import urllib.request
from typing import Dict, Any

# Configuração do logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Variáveis de ambiente e constantes
# Usando um modelo mais recente e econômico como padrão
DEFAULT_MODEL = "text-embedding-3-small"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/embeddings"

def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    Função Lambda que atua como um proxy seguro e inteligente para a API de Embeddings da OpenAI.
    Valida a entrada, aplica padrões e encaminha a requisição.
    """
    if not OPENAI_API_KEY:
        logger.error("A variável de ambiente OPENAI_API_KEY não foi definida.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Erro de configuração do servidor."})
        }

    request_id = context.aws_request_id
    logger.info(f"Iniciando a execução do proxy para OpenAI com request_id: {request_id}")

    # 1. Validação e parsing do corpo da requisição
    try:
        # O corpo vem como uma string, precisamos convertê-lo para um dicionário Python
        body = json.loads(event.get("body", "{}"))
        if not isinstance(body, dict):
            raise json.JSONDecodeError("O corpo deve ser um objeto JSON.", "", 0)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Erro de parsing no JSON do corpo da requisição: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Corpo da requisição malformado ou ausente."})
        }

    # 2. Verificação dos parâmetros da API OpenAI
    input_text = body.get("input")
    if not input_text:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "O parâmetro 'input' é obrigatório."})
        }
    
    # Valida se 'input' é string ou lista de strings, conforme a documentação
    if not (isinstance(input_text, str) or (isinstance(input_text, list) and all(isinstance(i, str) for i in input_text))):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "O parâmetro 'input' deve ser uma string ou um array de strings."})
        }

    # 3. Construção do payload para a OpenAI
    payload = {
        "input": input_text,
        "model": body.get("model", DEFAULT_MODEL),
        # Boa prática: adicionar um identificador único do usuário final para monitoramento de abuso
        "user": f"lambda-proxy-user-{request_id}"
    }
    
    # Adiciona parâmetros opcionais se eles existirem na requisição
    if "encoding_format" in body:
        payload["encoding_format"] = body["encoding_format"]
    if "dimensions" in body:
        payload["dimensions"] = body["dimensions"]

    logger.info(f"Payload sendo enviado para a OpenAI: {json.dumps(payload)}")

    # 4. Requisição para a API da OpenAI
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    
    try:
        # Converte o dicionário do payload de volta para uma string JSON codificada em bytes
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OPENAI_URL, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=25) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
            logger.info(f"Resposta da OpenAI recebida com status: {status_code}")
            return {
                "statusCode": status_code,
                "body": response_body
            }

    except urllib.error.HTTPError as e:
        # Captura erros HTTP da OpenAI (4xx, 5xx)
        error_body = e.read().decode("utf-8")
        logger.error(f"Erro HTTP da OpenAI: Status {e.code}, Corpo: {error_body}")
        return {
            "statusCode": e.code,
            "body": error_body
        }
    except Exception as e:
        logger.error(f"Erro inesperado no proxy: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Erro inesperado ao processar a requisição."})
        }