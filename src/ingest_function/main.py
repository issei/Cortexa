import json
import logging
import os
import boto3
import psycopg2
from psycopg2.extras import execute_batch

# Configuração do logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Variáveis globais para cache
NEON_DB_CONNECTION_STRING = None
OPENAI_PROXY_LAMBDA_ARN = None
LAMBDA_CLIENT = None
DB_CONNECTION = None

def _initialize():
    """Inicializa as variáveis de ambiente e clientes."""
    global NEON_DB_CONNECTION_STRING, OPENAI_PROXY_LAMBDA_ARN, LAMBDA_CLIENT
    if LAMBDA_CLIENT is None:
        logger.info("Inicializando clientes e variáveis de ambiente.")
        NEON_DB_CONNECTION_STRING = os.environ.get("NEON_DB_CONNECTION_STRING")
        OPENAI_PROXY_LAMBDA_ARN = os.environ.get("OPENAI_PROXY_LAMBDA_ARN")
        if not NEON_DB_CONNECTION_STRING or not OPENAI_PROXY_LAMBDA_ARN:
            logger.error("Variáveis de ambiente NEON_DB_CONNECTION_STRING ou OPENAI_PROXY_LAMBDA_ARN não definidas.")
            return False
        LAMBDA_CLIENT = boto3.client('lambda')
    return True

def _get_db_connection():
    """Estabelece e cacheia a conexão com o banco de dados."""
    global DB_CONNECTION
    if DB_CONNECTION is None or DB_CONNECTION.closed != 0:
        logger.info("Conectando ao banco de dados Neon.")
        try:
            DB_CONNECTION = psycopg2.connect(NEON_DB_CONNECTION_STRING)
        except psycopg2.Error as e:
            logger.error(f"Não foi possível conectar ao banco de dados: {e}")
            return None
    return DB_CONNECTION

def chunk_text(text, chunk_size=512, chunk_overlap=50):
    """Divide um texto em chunks com sobreposição."""
    if not isinstance(text, str):
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start += chunk_size - chunk_overlap
        if start >= len(text):
            break
    return [c for c in chunks if c]

def get_embedding(text_chunk, lambda_client, proxy_arn):
    """Invoca a Lambda de proxy para obter o embedding."""
    payload = {
        "body": json.dumps({
            "input": text_chunk,
            "model": "text-embedding-3-small"
        })
    }
    response = lambda_client.invoke(
        FunctionName=proxy_arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    response_payload = json.loads(response['Payload'].read().decode('utf-8'))

    if response_payload.get("statusCode") != 200:
        logger.error(f"Proxy retornou erro: {response_payload.get('body')}")
        raise Exception(f"Failed to get embedding: {response_payload.get('body')}")

    embedding_body = json.loads(response_payload["body"])
    # A API da OpenAI retorna uma lista de embeddings, pegamos o primeiro.
    return embedding_body['data'][0]['embedding']

def lambda_handler(event, context):
    """
    Lambda para ingerir texto, gerar embeddings e armazenar no Neon DB.
    """
    if not _initialize():
        return {"statusCode": 500, "body": json.dumps({"error": "Erro de configuração do servidor."})}

    try:
        body = json.loads(event.get("body", "{}"))
        knowledge_base_id = body.get("knowledgeBaseId")
        text = body.get("text")
        if not knowledge_base_id:
            return {"statusCode": 400, "body": json.dumps({"error": "O campo 'knowledgeBaseId' é obrigatório."})}
        if not text:
            return {"statusCode": 400, "body": json.dumps({"error": "O campo 'text' é obrigatório."})}
    except (json.JSONDecodeError, AttributeError):
        return {"statusCode": 400, "body": json.dumps({"error": "Corpo da requisição inválido."})}

    logger.info(f"Iniciando ingestão para a base de conhecimento: {knowledge_base_id}")

    text_chunks = chunk_text(text)
    if not text_chunks:
        return {"statusCode": 400, "body": json.dumps({"error": "Texto para ingestão está vazio ou inválido."})}

    logger.info(f"Texto dividido em {len(text_chunks)} chunks.")

    records_to_insert = []
    try:
        for chunk in text_chunks:
            embedding = get_embedding(chunk, LAMBDA_CLIENT, OPENAI_PROXY_LAMBDA_ARN)
            records_to_insert.append((knowledge_base_id, chunk, embedding))

        logger.info(f"Embeddings gerados para {len(records_to_insert)} chunks.")

    except Exception as e:
        logger.error(f"Erro ao obter embeddings: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    conn = _get_db_connection()
    if not conn:
        return {"statusCode": 500, "body": json.dumps({"error": "Não foi possível conectar ao banco de dados."})}

    try:
        with conn.cursor() as cur:
            sql = "INSERT INTO knowledge_chunks (knowledge_base_id, content, embedding) VALUES (%s, %s, %s)"
            execute_batch(cur, sql, records_to_insert)
        conn.commit()
        logger.info(f"Sucesso! {len(records_to_insert)} chunks inseridos no banco de dados.")

    except psycopg2.Error as e:
        logger.error(f"Erro de banco de dados: {e}")
        if conn:
            conn.rollback()
        return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {e}"})}

    finally:
        # A conexão não é fechada aqui para permitir reutilização em 'warm' invocations.
        pass

    return {
        "statusCode": 202,
        "body": json.dumps({
            "status": "accepted",
            "message": f"{len(records_to_insert)} chunks foram processados e agendados para inserção."
        })
    }
