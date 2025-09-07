import json
import os
import pytest
from unittest.mock import MagicMock

# Adiciona o diretório src ao sys.path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / 'src' / 'query_function'))

from main import lambda_handler

# --- Testes para a Função Lambda: query_function ---

@pytest.fixture
def mock_dependencies(mocker):
    """Fixture para mockar as dependências externas (boto3, psycopg2)."""
    # Mock do boto3
    mock_lambda_client = MagicMock()
    mocker.patch('main.boto3.client', return_value=mock_lambda_client)

    # Mock do psycopg2
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Simula o retorno da busca no banco de dados
    mock_cursor.fetchall.return_value = [
        ("chunk de texto relevante 1", 0.95, {"page": 1}),
        ("chunk de texto relevante 2", 0.92, None)
    ]
    # O cursor é usado em um bloco 'with', então precisamos mockar o context manager
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mocker.patch('main.psycopg2.connect', return_value=mock_conn)

    # Mock das variáveis de ambiente
    mocker.patch.dict(os.environ, {
        "NEON_DB_CONNECTION_STRING": "fake_db_string",
        "OPENAI_PROXY_LAMBDA_ARN": "arn:aws:lambda:us-east-1:123456789012:function:fake-proxy"
    })

    return mock_lambda_client, mock_cursor

def test_query_success_path(mock_dependencies):
    """
    Testa o caminho feliz da função de consulta.
    """
    mock_lambda_client, mock_cursor = mock_dependencies
    proxy_response_payload = json.dumps({
        "statusCode": 200,
        "body": json.dumps({"data": [{"embedding": [0.2] * 1536}]})
    }).encode('utf-8')
    mock_lambda_client.invoke.return_value = {
        'Payload': MagicMock(read=lambda: proxy_response_payload)
    }

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "qual é a pergunta de teste?",
            "top_k": 5
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "results" in body
    assert len(body["results"]) == 2
    assert body["results"][0]["content"] == "chunk de texto relevante 1"
    assert body["results"][0]["score"] == 0.95
    assert body["results"][0]["metadata"] == {"page": 1}

    # Verifica se a lambda de proxy foi chamada
    mock_lambda_client.invoke.assert_called_once()
    # Verifica se a consulta ao DB foi feita
    mock_cursor.execute.assert_called_once()
    # Verifica se o `top_k` foi usado na query SQL
    assert mock_cursor.execute.call_args.args[1][2] == 5


def test_query_default_top_k(mock_dependencies):
    """
    Testa se o valor padrão de `top_k` é usado quando não é fornecido.
    """
    mock_lambda_client, mock_cursor = mock_dependencies
    proxy_response_payload = json.dumps({
        "statusCode": 200,
        "body": json.dumps({"data": [{"embedding": [0.2] * 1536}]})
    }).encode('utf-8')
    mock_lambda_client.invoke.return_value = {
        'Payload': MagicMock(read=lambda: proxy_response_payload)
    }

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "teste sem top_k"
        })
    }

    lambda_handler(event, None)

    # O padrão definido na função é 3
    assert mock_cursor.execute.call_args.args[1][2] == 3


def test_query_missing_parameters():
    """
    Testa se a função retorna erro 400 se parâmetros essenciais estiverem faltando.
    """
    # Caso 1: Falta 'text'
    event_no_text = {
        "body": json.dumps({"knowledgeBaseId": "kb-123"})
    }
    response_no_text = lambda_handler(event_no_text, None)
    assert response_no_text["statusCode"] == 400
    assert "text" in json.loads(response_no_text["body"])["error"]

    # Caso 2: Falta 'knowledgeBaseId'
    event_no_kb = {
        "body": json.dumps({"text": "uma pergunta"})
    }
    response_no_kb = lambda_handler(event_no_kb, None)
    assert response_no_kb["statusCode"] == 400
    assert "knowledgeBaseId" in json.loads(response_no_kb["body"])["error"]


def test_query_proxy_invocation_error(mock_dependencies):
    """
    Testa o tratamento de erro se a invocação da Lambda de proxy falhar.
    """
    mock_lambda_client, mock_cursor = mock_dependencies
    mock_lambda_client.invoke.side_effect = Exception("Proxy invocation failed")

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "esta query vai falhar"
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 500
    assert "Proxy invocation failed" in json.loads(response["body"])["error"]
    # Garante que não tentamos consultar o DB se o embedding falhou
    mock_cursor.execute.assert_not_called()
