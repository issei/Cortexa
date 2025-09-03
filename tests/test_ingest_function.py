import json
import os
import pytest
from unittest.mock import MagicMock, patch

# Adiciona o diretório src ao sys.path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / 'src' / 'ingest_function'))

# Importa o handler e outras funções
from main import lambda_handler, chunk_text

# --- Testes para a Função de Chunking ---

def test_chunk_text():
    """
    Testa a lógica de divisão de texto em chunks com sobreposição.
    """
    text = "um dois três quatro cinco seis sete oito nove dez"
    # Cada palavra tem 3 ou 4 ou 5 letras + 1 espaço = 4 a 6 caracteres
    # Chunk size 20 deveria pegar 4 palavras (aprox 4*5=20)
    # Overlap 5 deveria recuar 1 palavra
    chunks = chunk_text(text, chunk_size=20, chunk_overlap=5)

    assert len(chunks) > 1
    assert chunks[0] == "um dois três quatro"
    # O overlap é em caracteres, não palavras. "quatro" tem 6. Overlap de 5.
    # O segundo chunk deve começar antes do fim do primeiro.
    assert "quatro" in chunks[1]
    assert chunks[1].startswith("quatro")


# --- Testes para a Função Lambda: ingest_function ---

@pytest.fixture
def mock_dependencies(mocker):
    """Fixture para mockar as dependências externas (boto3, psycopg2)."""
    # Mock do boto3
    mock_lambda_client = MagicMock()
    # Simula uma resposta bem-sucedida do proxy
    proxy_response_payload = json.dumps({
        "statusCode": 200,
        "body": json.dumps({"embedding": [0.1] * 1536})
    })
    mock_lambda_client.invoke.return_value = {
        'Payload': MagicMock(read=lambda: proxy_response_payload)
    }
    mocker.patch('main.boto3.client', return_value=mock_lambda_client)

    # Mock do psycopg2
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('main.psycopg2.connect', return_value=mock_conn)

    # Mock das variáveis de ambiente
    mocker.patch.dict(os.environ, {
        "NEON_DB_CONNECTION_STRING": "fake_db_string",
        "OPENAI_PROXY_LAMBDA_ARN": "arn:aws:lambda:us-east-1:123456789012:function:fake-proxy"
    })

    return mock_lambda_client, mock_cursor

def test_ingest_success_path(mock_dependencies):
    """
    Testa o caminho feliz da função de ingestão.
    """
    mock_lambda_client, mock_cursor = mock_dependencies

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este é um texto de teste para a ingestão. Ele tem mais de um chunk."
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "accepted"
    assert "chunks" in body["message"]

    # Verifica se a lambda de proxy foi chamada (mais de uma vez para o texto)
    assert mock_lambda_client.invoke.call_count > 0
    # Verifica se a conexão com o DB e o commit foram chamados
    assert mock_cursor.execute.call_count == 1
    assert mock_cursor.connection.commit.call_count == 1


def test_ingest_missing_parameters():
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
        "body": json.dumps({"text": "um texto qualquer"})
    }
    response_no_kb = lambda_handler(event_no_kb, None)
    assert response_no_kb["statusCode"] == 400
    assert "knowledgeBaseId" in json.loads(response_no_kb["body"])["error"]


def test_ingest_proxy_invocation_error(mock_dependencies):
    """
    Testa o tratamento de erro se a invocação da Lambda de proxy falhar.
    """
    mock_lambda_client, mock_cursor = mock_dependencies
    # Simula um erro na invocação da Lambda
    proxy_error_payload = json.dumps({
        "statusCode": 500,
        "body": json.dumps({"error": "OpenAI API is down"})
    })
    mock_lambda_client.invoke.return_value = {
        'Payload': MagicMock(read=lambda: proxy_error_payload)
    }

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este texto causará um erro."
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 500
    assert "Failed to get embedding" in json.loads(response["body"])["error"]
    # Garante que, em caso de erro, não tentamos fazer o commit no DB
    mock_cursor.connection.commit.assert_not_called()


def test_ingest_database_error(mock_dependencies):
    """
    Testa o tratamento de erro se a operação de banco de dados falhar.
    """
    mock_lambda_client, mock_cursor = mock_dependencies
    # Simula um erro no execute do cursor
    mock_cursor.execute.side_effect = Exception("Database connection failed")

    event = {
        "body": json.dumps({
            "knowledgeBaseId": "kb-123",
            "text": "Este texto vai falhar no DB."
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 500
    assert "Database error" in json.loads(response["body"])["error"]
    # Garante que o rollback foi chamado
    mock_cursor.connection.rollback.assert_called_once()
