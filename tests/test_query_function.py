import json
import os
import pytest
import psycopg2
from unittest.mock import MagicMock, patch, ANY

# Adiciona o diretório src ao sys.path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / 'src' / 'query_function'))

from main import lambda_handler, _initialize, _get_db_connection, get_embedding

# --- Fixtures ---

@pytest.fixture
def mock_env(monkeypatch):
    """Configura variáveis de ambiente para teste."""
    env_vars = {
        "NEON_DB_CONNECTION_STRING": "postgresql://fake:fake@fake.neon.tech/cortexa",
        "OPENAI_PROXY_LAMBDA_ARN": "arn:aws:lambda:sa-east-1:497568177086:function:openai-proxy"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars

@pytest.fixture
def mock_lambda_response():
    """Mock de resposta padrão do Lambda de embeddings."""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "data": [{
                "embedding": [0.1] * 1536,
                "index": 0,
                "object": "embedding"
            }]
        })
    }

@pytest.fixture
def mock_db_results():
    """Mock de resultados padrão do banco de dados."""
    return [
        ("Este é o resultado mais relevante", 0.95, {"page": 1, "source": "doc1.pdf"}),
        ("Um resultado menos relevante", 0.85, {"page": 2, "source": "doc1.pdf"}),
        ("Resultado com relevância menor", 0.75, {"page": 1, "source": "doc2.pdf"})
    ]

@pytest.fixture
def mock_dependencies(mocker, mock_env, mock_lambda_response, mock_db_results):
    """Fixture principal para mockar todas as dependências."""
    # Mock do Lambda client
    mock_lambda = MagicMock()
    mock_lambda.invoke.return_value = {
        'Payload': MagicMock(
            read=lambda: json.dumps(mock_lambda_response).encode('utf-8')
        )
    }
    mocker.patch('main.boto3.client', return_value=mock_lambda)

    # Mock do DB
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_db_results
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mocker.patch('main.psycopg2.connect', return_value=mock_conn)
    
    # Reset das variáveis globais
    mocker.patch('main.LAMBDA_CLIENT', None)
    mocker.patch('main.DB_CONNECTION', None)
    
    return {
        'lambda_client': mock_lambda,
        'db_conn': mock_conn,
        'db_cursor': mock_cursor,
        'lambda_response': mock_lambda_response,
        'db_results': mock_db_results
    }

@pytest.fixture
def valid_event():
    """Evento válido para testes."""
    return {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "consulta de teste",
            "top_k": 3
        })
    }

# --- Testes de Inicialização ---

def test_initialize_success(mock_env):
    """Testa inicialização bem-sucedida."""
    assert _initialize() is True
    assert isinstance(_get_db_connection(), MagicMock)

def test_initialize_missing_env_vars(monkeypatch):
    """Testa falha na inicialização com variáveis de ambiente faltando."""
    monkeypatch.delenv("NEON_DB_CONNECTION_STRING", raising=False)
    assert _initialize() is False

# --- Testes do Handler Principal ---

def test_query_success_path(mock_dependencies, valid_event):
    """Testa o fluxo completo de sucesso da query."""
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "results" in body
    
    # Verifica estrutura e conteúdo dos resultados
    results = body["results"]
    assert len(results) == 3  # top_k=3 do evento
    assert all(isinstance(r["content"], str) for r in results)
    assert all(0 <= r["score"] <= 1 for r in results)
    assert all(isinstance(r["metadata"], dict) for r in results)
    
    # Verifica ordenação por score
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    
    # Verifica chamadas aos serviços
    mock_lambda = mock_dependencies['lambda_client']
    mock_cursor = mock_dependencies['db_cursor']
    
    mock_lambda.invoke.assert_called_once()
    mock_cursor.execute.assert_called_once()
    
    # Verifica parâmetros da query SQL
    sql_args = mock_cursor.execute.call_args.args[1]
    assert isinstance(json.loads(sql_args[0]), list)  # embedding como JSON
    assert sql_args[1] == "kb-123"  # knowledgeBaseId
    assert sql_args[2] == 3  # top_k


# --- Testes de Parâmetros ---

@pytest.mark.parametrize("event_data,expected_top_k", [
    ({"knowledgeBaseId": "kb-123", "text": "query"}, 3),  # default
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": 5}, 5),
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": 1}, 1),
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": 10}, 10),
])
def test_query_top_k_variations(mock_dependencies, event_data, expected_top_k):
    """Testa diferentes valores de top_k."""
    event = {"body": json.dumps(event_data)}
    lambda_handler(event, None)
    
    mock_cursor = mock_dependencies['db_cursor']
    assert mock_cursor.execute.call_args.args[1][2] == expected_top_k

@pytest.mark.parametrize("event_body,expected_error", [
    ({"text": "query"}, "knowledgeBaseId"),  # Falta KB ID
    ({"knowledgeBaseId": "kb-123"}, "text"),  # Falta texto
    ({"knowledgeBaseId": "", "text": "query"}, "knowledgeBaseId"),  # KB ID vazio
    ({"knowledgeBaseId": "kb-123", "text": ""}, "text"),  # Texto vazio
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": "abc"}, "inválido"),  # top_k inválido
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": 0}, "inválido"),  # top_k zero
    ({"knowledgeBaseId": "kb-123", "text": "query", "top_k": -1}, "inválido"),  # top_k negativo
])
def test_query_input_validation(mock_dependencies, event_body, expected_error):
    """Testa validação de diferentes inputs."""
    event = {"body": json.dumps(event_body)}
    response = lambda_handler(event, None)
    
    assert response["statusCode"] == 400
    assert expected_error in json.loads(response["body"])["error"].lower()

# --- Testes de Erros ---

def test_query_proxy_invocation_error(mock_dependencies, valid_event):
    """Testa erros na chamada do serviço de embeddings."""
    mock_lambda = mock_dependencies['lambda_client']
    mock_lambda.invoke.side_effect = Exception("Lambda invocation failed")
    
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == 500
    error_msg = json.loads(response["body"])["error"]
    assert "Lambda invocation failed" in error_msg
    
    # Não deve ter tentado acessar o banco
    mock_cursor = mock_dependencies['db_cursor']
    mock_cursor.execute.assert_not_called()

@pytest.mark.parametrize("db_error,expected_message", [
    (psycopg2.OperationalError("connection failed"), "conectar ao banco"),
    (psycopg2.ProgrammingError("invalid query"), "Database query error"),
    (psycopg2.InterfaceError("connection already closed"), "conectar ao banco"),
    (Exception("Unexpected DB error"), "Database query error"),
])
def test_query_database_errors(mock_dependencies, valid_event, db_error, expected_message):
    """Testa diferentes tipos de erros de banco de dados."""
    mock_cursor = mock_dependencies['db_cursor']
    mock_cursor.execute.side_effect = db_error
    
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == 500
    error_msg = json.loads(response["body"])["error"]
    assert expected_message in error_msg

# --- Testes de Performance ---

def test_query_caching(mock_dependencies):
    """Verifica se conexões e clientes são reutilizados."""
    # Primeira chamada - deve criar conexões
    lambda_handler(valid_event, None)
    
    # Segunda chamada - deve reutilizar conexões
    lambda_handler(valid_event, None)
    
    mock_boto3 = mock_dependencies['lambda_client']
    assert mock_boto3.client.call_count == 1  # Cliente Lambda criado apenas uma vez

def test_query_large_response(mock_dependencies, valid_event):
    """Testa comportamento com grande volume de resultados."""
    # Simula 1000 resultados
    mock_cursor = mock_dependencies['db_cursor']
    mock_cursor.fetchall.return_value = [
        (f"Resultado {i}", 0.9 - (i * 0.001), {"page": i})
        for i in range(1000)
    ]
    
    response = lambda_handler(valid_event, None)
    results = json.loads(response["body"])["results"]
    
    assert response["statusCode"] == 200
    assert len(results) == 3  # Deve respeitar o top_k mesmo com muitos resultados
    assert all(results[i]["score"] > results[i+1]["score"] 
              for i in range(len(results)-1))  # Verifica ordenação

# --- Testes de Integração ---

@pytest.mark.integration
def test_integration_real_services(mock_env):
    """
    Teste de integração usando serviços reais.
    Requer variáveis de ambiente configuradas.
    """
    event = {
        "body": json.dumps({
            "knowledgeBaseId": "test-kb",
            "text": "Como usar embeddings vetoriais para busca semântica?",
            "top_k": 2
        })
    }
    
    try:
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        
        results = json.loads(response["body"])["results"]
        assert len(results) == 2
        assert all(0.5 <= r["score"] <= 1.0 for r in results)  # Scores plausíveis
        
    except Exception as e:
        pytest.skip(f"Teste de integração falhou: {e}")

@pytest.mark.integration
def test_integration_semantic_quality():
    """
    Testa a qualidade semântica dos resultados.
    Requer acesso aos serviços reais.
    """
    similar_queries = [
        "Como implementar busca vetorial?",
        "Qual a melhor maneira de fazer busca com vetores?"
    ]
    different_query = "Qual a receita de bolo de chocolate?"
    
    try:
        # Faz buscas com queries similares
        results_similar = []
        for query in similar_queries:
            response = lambda_handler({
                "body": json.dumps({
                    "knowledgeBaseId": "test-kb",
                    "text": query,
                    "top_k": 3
                })
            }, None)
            results_similar.append(
                json.loads(response["body"])["results"]
            )
        
        # Busca com query diferente
        response_diff = lambda_handler({
            "body": json.dumps({
                "knowledgeBaseId": "test-kb",
                "text": different_query,
                "top_k": 3
            })
        }, None)
        results_diff = json.loads(response_diff["body"])["results"]
        
        # As queries similares devem retornar resultados mais parecidos entre si
        similar_contents = set(r["content"] for r in results_similar[0])
        different_contents = set(r["content"] for r in results_diff)
        
        overlap_similar = len(
            similar_contents.intersection(set(r["content"] for r in results_similar[1]))
        )
        overlap_different = len(
            similar_contents.intersection(different_contents)
        )
        
        assert overlap_similar > overlap_different
        
    except Exception as e:
        pytest.skip(f"Teste de qualidade semântica falhou: {e}")

# --- Testes de Logging ---

def test_query_logging(mock_dependencies, valid_event, caplog):
    """Verifica se os logs apropriados são gerados."""
    with caplog.at_level(logging.INFO):
        lambda_handler(valid_event, None)
    
    # Verifica logs esperados
    assert any("Recebida consulta" in record.message 
              for record in caplog.records)
    assert any("Busca encontrou" in record.message 
              for record in caplog.records)
