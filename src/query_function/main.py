import json
import logging
import os
import boto3
import psycopg2

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
            logger.error("Variáveis de ambiente não definidas.")
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

def get_embedding(text_query, lambda_client, proxy_arn):
    """Invoca a Lambda de proxy para obter o embedding da consulta."""
    payload = {
        "body": json.dumps({
            "input": text_query,
            "model": "text-embedding-3-small"
        })
    }
    response = lambda_client.invoke(
        FunctionName=proxy_arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    response_payload = json.load(response['Payload'])

    if response_payload.get("statusCode") != 200:
        logger.error(f"Proxy retornou erro: {response_payload.get('body')}")
        raise Exception(f"Failed to get embedding for query: {response_payload.get('body')}")

    embedding_body = json.loads(response_payload["body"])
    return embedding_body['data'][0]['embedding']


def lambda_handler(event, context):
    """
    Lambda para receber uma query, gerar seu embedding e fazer a busca vetorial.
    """
    if not _initialize():
        return {"statusCode": 500, "body": json.dumps({"error": "Erro de configuração do servidor."})}

    try:
        body = json.loads(event.get("body", "{}"))
        knowledge_base_id = body.get("knowledgeBaseId")
        query_text = body.get("query")
        top_k = int(body.get("top_k", 3))

        if not knowledge_base_id:
            return {"statusCode": 400, "body": json.dumps({"error": "O campo 'knowledgeBaseId' é obrigatório."})}
        if not query_text:
            return {"statusCode": 400, "body": json.dumps({"error": "O campo 'query' é obrigatório."})}
    except (json.JSONDecodeError, AttributeError, ValueError):
        return {"statusCode": 400, "body": json.dumps({"error": "Corpo da requisição inválido."})}

    logger.info(f"Recebida consulta para a base: {knowledge_base_id}")

    try:
        query_embedding = get_embedding(query_text, LAMBDA_CLIENT, OPENAI_PROXY_LAMBDA_ARN)
    except Exception as e:
        logger.error(f"Erro ao obter embedding da consulta: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    conn = _get_db_connection()
    if not conn:
        return {"statusCode": 500, "body": json.dumps({"error": "Não foi possível conectar ao banco de dados."})}

    results = []
    try:
        with conn.cursor() as cur:
            # A query usa o operador de distância de cosseno (<=>) do pg_vector
            # 1 - distancia_cosseno = similaridade_cosseno
            sql = """
                SELECT content, 1 - (embedding <=> %s) as score, metadata
                FROM knowledge_chunks
                WHERE knowledge_base_id = %s
                ORDER BY score DESC
                LIMIT %s;
            """
            # O embedding precisa ser passado como string para a query
            cur.execute(sql, (json.dumps(query_embedding), knowledge_base_id, top_k))

            for row in cur.fetchall():
                results.append({
                    "content": row[0],
                    "score": row[1],
                    "metadata": row[2]
                })
        logger.info(f"Busca encontrou {len(results)} resultados.")

    except psycopg2.Error as e:
        logger.error(f"Erro na busca no banco de dados: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database query error: {e}"})}

    return {
        "statusCode": 200,
        "body": json.dumps({"results": results})
    }
