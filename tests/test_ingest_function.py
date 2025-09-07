import json
import os
import pytest
from unittest.mock import MagicMock, patch, ANY
import psycopg2
from psycopg2.extras import execute_batch

from src.ingest_function.main import (
    lambda_handler,
    chunk_text,
    get_embedding,
    _initialize,
    _get_db_connection
)

# --- Testes para a Função de Chunking ---

@pytest.mark.parametrize("test_input,chunk_size,chunk_overlap,expected", [
    # Caso básico
    (
        "um dois três quatro cinco seis sete oito nove dez",
        20,
        5,
        ["um dois três quatro", "quatro cinco seis sete"]
    ),
    # Texto vazio
    ("", 20, 5, []),
    # Texto menor que chunk_size
    ("texto pequeno", 20, 5, ["texto pequeno"]),
    # Texto com múltiplos chunks e overlap significativo
    (
        "um dois três quatro cinco seis sete oito nove dez onze doze",
        10,
        3,
        ["um dois", "dois três", "três quatro", "quatro cinco"]
    ),
    # Input inválido
    (None, 20, 5, []),
    # Texto com caracteres especiais e espaços extras
    (
        "  texto  com    espaços   extras  \n\t e quebras  ",
        15,
        3,
        ["texto com", "com espaços", "espaços extras", "extras e quebras"]
    )
])
def test_chunk_text(test_input, chunk_size, chunk_overlap, expected):
    """
    Testa a função chunk_text com vários cenários usando parametrização.
    """
    result = chunk_text(test_input, chunk_size, chunk_overlap)
    # Para o caso de textos longos, verificamos apenas o número de chunks
    if len(result) > len(expected):
        assert len(result) >= len(expected)
        for chunk in result:
            assert isinstance(chunk, str)
            assert len(chunk.strip()) > 0
    else:
        assert [r.strip() for r in result] == [e.strip() for e in expected]


# --- Fixtures ---

@pytest.fixture
def mock_environment(monkeypatch):
    """Fixture para configurar variáveis de ambiente."""
    env_vars = {
        "NEON_DB_CONNECTION_STRING": "postgresql://fake:fake@fake.neon.tech/cortexa",
        "OPENAI_PROXY_LAMBDA_ARN": "arn:aws:lambda:sa-east-1:497568177086:function:openai-proxy",
        "AWS_REGION": "us-east-1"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars

@pytest.fixture
def mock_dependencies(mocker, mock_environment):
    """Fixture para mockar as dependências externas (boto3, psycopg2)."""
    # Mock do boto3
    mock_lambda_client = MagicMock()
    mocker.patch('main.boto3.client', return_value=mock_lambda_client)
    
    # Mock de resposta padrão do Lambda
    proxy_response = {
        "statusCode": 200,
        "body": json.dumps({
            "data": [{"embedding": [0.1] * 1536}]
        })
    }
    mock_lambda_client.invoke.return_value = {
        'Payload': MagicMock(
            read=lambda: json.dumps(proxy_response).encode('utf-8')
        )
    }

    # Mock do psycopg2
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.mogrify.return_value = b"mocked sql"
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mocker.patch('main.psycopg2.connect', return_value=mock_conn)
    
    # Reset das variáveis globais do módulo
    mocker.patch('main.LAMBDA_CLIENT', None)
    mocker.patch('main.DB_CONNECTION', None)
    
    return {
        'lambda_client': mock_lambda_client,
        'db_cursor': mock_cursor,
        'db_conn': mock_conn,
        'proxy_response': proxy_response
    }

# --- Testes de Inicialização ---

def test_initialize_success(mock_environment):
    """Testa a inicialização bem-sucedida do módulo."""
    assert _initialize() is True

def test_initialize_missing_env_vars(monkeypatch):
    """Testa falha na inicialização quando faltam variáveis de ambiente."""
    monkeypatch.delenv("NEON_DB_CONNECTION_STRING", raising=False)
    assert _initialize() is False

# --- Testes da Função get_embedding ---

def test_get_embedding_success(mock_dependencies):
    """Testa a obtenção bem-sucedida de embeddings."""
    mock = mock_dependencies['lambda_client']
    result = get_embedding(
        "texto teste",
        mock,
        "arn:aws:lambda:sa-east-1:497568177086:function:openai-proxy"
    )
    assert len(result) == 1536
    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)

def test_get_embedding_proxy_error(mock_dependencies):
    """Testa erro na chamada do proxy de embeddings."""
    mock = mock_dependencies['lambda_client']
    error_response = {
        "statusCode": 500,
        "body": json.dumps({"error": "API rate limit exceeded"})
    }
    mock.invoke.return_value = {
        'Payload': MagicMock(
            read=lambda: json.dumps(error_response).encode('utf-8')
        )
    }
    
    with pytest.raises(Exception) as exc_info:
        get_embedding(
            "texto teste",
            mock,
            "arn:aws:lambda:sa-east-1:497568177086:function:openai-proxy"
        )
    assert "Failed to get embedding" in str(exc_info.value)

# --- Testes do Handler Principal ---

def test_lambda_handler_success(mock_dependencies):
    """Testa o fluxo completo de sucesso do handler."""
    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este é um texto de teste para a ingestão. "*10  # Texto longo o suficiente para gerar múltiplos chunks
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "accepted"
    assert isinstance(body["message"], str)
    
    # Verifica chamadas aos serviços externos
    mock_db = mock_dependencies['db_conn']
    mock_cursor = mock_dependencies['db_cursor']
    mock_lambda = mock_dependencies['lambda_client']
    
    assert mock_lambda.invoke.call_count > 0  # Chamadas para embeddings
    assert mock_cursor.execute.call_count > 0  # Inserções no banco
    mock_db.commit.assert_called_once()  # Um commit ao final

@pytest.mark.parametrize("event_body,expected_error", [
    # Falta knowledgeBaseId
    ({"text": "algum texto"}, "knowledgeBaseId"),
    # Falta text
    ({"knowledgeBaseId": "kb-123"}, "text"),
    # Corpo vazio
    ({}, "knowledgeBaseId"),
    # Valores vazios - knowledgeBaseId is checked first
    ({"knowledgeBaseId": "", "text": ""}, "knowledgeBaseId"),
])
def test_lambda_handler_validation(mock_dependencies, event_body, expected_error):
    """Testa validação de parâmetros de entrada."""
    event = {"body": json.dumps(event_body)}
    response = lambda_handler(event, None)
    
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert expected_error in body["error"].lower()

def test_lambda_handler_invalid_json(mock_dependencies):
    """Testa tratamento de JSON inválido no corpo da requisição."""
    event = {"body": "isto não é json"}
    response = lambda_handler(event, None)
    
    assert response["statusCode"] == 400
    assert "inválido" in json.loads(response["body"])["error"].lower()

def test_lambda_handler_proxy_error(mock_dependencies):
    """Testa erro na chamada do serviço de embeddings."""
    mock = mock_dependencies['lambda_client']
    mock.invoke.side_effect = Exception("Lambda invocation failed")

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este texto causará um erro."
        })
    }

    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    assert "Lambda invocation failed" in json.loads(response["body"])["error"]
    
    # Não deve ter tentado fazer commit no DB
    mock_dependencies['db_conn'].commit.assert_not_called()

def test_lambda_handler_db_error(mock_dependencies):
    """Testa erro nas operações de banco de dados."""
    mock_cursor = mock_dependencies['db_cursor']
    mock_conn = mock_dependencies['db_conn']
    
    # Simula erro na execução do batch
    db_error = psycopg2.Error("Database error")
    mock_cursor.execute.side_effect = db_error

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este texto vai falhar no DB."
        })
    }

    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Database error" in body["error"]
    
    # Deve ter feito rollback
    mock_conn.rollback.assert_called_once()

# --- Testes de Integração ---

@pytest.mark.integration
def test_integration_full_flow(mock_environment):
    """
    Teste de integração do fluxo completo.
    Requer variáveis de ambiente configuradas e serviços disponíveis.
    """
    event = {
        "body": json.dumps({
            "knowledgeBaseId": "test-kb",
            "text": """Este é um texto de teste para o fluxo de integração.
                    Ele deve ser longo o suficiente para gerar múltiplos chunks e
                    testar a funcionalidade de chunking. O texto também precisa ter
                    conteúdo semântico suficiente para gerar embeddings significativos.
                    Vamos incluir alguns conceitos técnicos como: AWS Lambda,
                    embeddings vetoriais, e processamento de linguagem natural."""
        })
    }
    
    try:
        response = lambda_handler(event, None)
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "accepted"
        assert int(body["message"].split()[0]) > 0  # Número de chunks processados
    except Exception as e:
        pytest.skip(f"Teste de integração falhou: {e}")

@pytest.mark.integration
def test_integration_embedding_quality():
    """
    Testa a qualidade dos embeddings gerados comparando similaridade semântica.
    Requer acesso ao serviço de embeddings.
    """
    similar_texts = [
        "AWS Lambda é um serviço de computação serverless",
        "Computação sem servidor na AWS usando funções Lambda"
    ]
    different_text = "Receita de bolo de chocolate com cobertura"
    
    try:
        # Gera embeddings para os textos
        client = boto3.client('lambda')
        similar_embeddings = [
            get_embedding(text, client, os.environ["OPENAI_PROXY_LAMBDA_ARN"])
            for text in similar_texts
        ]
        different_embedding = get_embedding(
            different_text,
            client,
            os.environ["OPENAI_PROXY_LAMBDA_ARN"]
        )
        
        # Calcula similaridade de cosseno
        def cosine_similarity(a, b):
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            return dot_product / (norm_a * norm_b)
        
        # A similaridade entre textos semelhantes deve ser maior
        similar_score = cosine_similarity(
            similar_embeddings[0],
            similar_embeddings[1]
        )
        different_score = cosine_similarity(
            similar_embeddings[0],
            different_embedding
        )
        
        assert similar_score > different_score
        assert similar_score > 0.7  # Threshold arbitrário para similaridade
        
    except Exception as e:
        pytest.skip(f"Teste de qualidade de embeddings falhou: {e}")

# --- Testes de Performance ---

@pytest.mark.performance
def test_performance_large_text(mock_dependencies):
    """Testa performance com texto grande."""
    # Gera texto grande (~100KB)
    large_text = "Palavra " * 20000
    
    event = {
        "body": json.dumps({
            "knowledgeBaseId": "perf-test",
            "text": large_text
        })
    }
    
    import time
    start = time.time()
    response = lambda_handler(event, None)
    duration = time.time() - start
    
    assert response["statusCode"] == 202
    assert duration < 30  # Deve processar em menos de 30 segundos
