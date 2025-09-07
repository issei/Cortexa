import json
import os
import pytest
import urllib3
from unittest.mock import MagicMock, patch
from urllib3.exceptions import RequestError, TimeoutError, MaxRetryError

# Adiciona o diretório src ao sys.path para permitir importações locais
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / 'src' / 'openai_embedding_proxy'))

# Importa o handler e funções auxiliares
from main import lambda_handler, _initialize
import main as main_module

# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset do estado global do módulo antes de cada teste."""
    main_module.API_KEY = None
    main_module.HTTP = None
    main_module.OPENAI_URL = "https://api.openai.com/v1/embeddings"

@pytest.fixture
def mock_env(monkeypatch):
    """Configura variáveis de ambiente para teste."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    return {"OPENAI_API_KEY": "test-key-12345"}

@pytest.fixture
def mock_http_success():
    """Mock do PoolManager para respostas de sucesso."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.data = json.dumps({
        "data": [{
            "embedding": [0.1] * 1536,
            "index": 0,
            "object": "embedding"
        }]
    }).encode('utf-8')
    
    mock_pool = MagicMock()
    mock_pool.request.return_value = mock_response
    return mock_pool

@pytest.fixture
def valid_event():
    """Evento válido para testes."""
    return {
        "body": json.dumps({
            "input": "Texto para embeddings",
            "model": "text-embedding-3-small"
        })
    }

# --- Testes de Inicialização ---

def test_initialize_success(mock_env):
    """Testa inicialização bem-sucedida."""
    assert _initialize() is True
    assert main_module.API_KEY == "test-key-12345"
    assert isinstance(main_module.HTTP, MagicMock)

def test_initialize_missing_key(monkeypatch):
    """Testa inicialização sem a chave API configurada."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _initialize() is False
    assert main_module.API_KEY is None

def test_initialize_idempotent(mock_env, mocker):
    """Testa que inicialização múltipla não recria recursos."""
    mock_pool = mocker.patch('urllib3.PoolManager')
    
    assert _initialize() is True
    first_http = main_module.HTTP
    
    assert _initialize() is True
    assert main_module.HTTP is first_http
    assert mock_pool.call_count == 1

# --- Testes do Handler Principal ---

def test_proxy_success_path(mocker, mock_env, mock_http_success, valid_event):
    """Testa o caminho feliz do proxy."""
    mocker.patch('main.urllib3.PoolManager', return_value=mock_http_success)
    
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == 200
    response_data = json.loads(response["body"])
    assert "data" in response_data
    assert len(response_data["data"][0]["embedding"]) == 1536
    
    mock_http_success.request.assert_called_once_with(
        "POST",
        main_module.OPENAI_URL,
        body=valid_event["body"],
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {mock_env['OPENAI_API_KEY']}",
        },
        timeout=25
    )

@pytest.mark.parametrize("test_input,expected_error", [
    ({"wrong_key": "test"}, "Corpo da requisição inválido"),
    (None, "Corpo da requisição inválido"),
    ({}, "Corpo da requisição inválido"),
])
def test_proxy_invalid_input(mocker, mock_env, test_input, expected_error):
    """Testa validação de input."""
    mocker.patch('main.urllib3.PoolManager', return_value=MagicMock())
    
    response = lambda_handler({"body": json.dumps(test_input)}, None)
    
    assert response["statusCode"] == 400
    assert expected_error in json.loads(response["body"])["error"]


# --- Testes de Erros da API ---

@pytest.mark.parametrize("status_code,error_message", [
    (401, {"error": {"message": "Invalid API key"}}),
    (429, {"error": {"message": "Rate limit exceeded"}}),
    (500, {"error": {"message": "Internal server error"}}),
])
def test_proxy_api_errors(mocker, mock_env, valid_event, status_code, error_message):
    """Testa propagação de erros da API OpenAI."""
    mock_http = MagicMock()
    mock_http.request.return_value = MagicMock(
        status=status_code,
        data=json.dumps(error_message).encode('utf-8')
    )
    mocker.patch('main.urllib3.PoolManager', return_value=mock_http)
    
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == status_code
    assert json.loads(response["body"]) == error_message

# --- Testes de Erros de Rede ---

@pytest.mark.parametrize("exception,expected_message", [
    (TimeoutError("Connection timeout"), "timeout"),
    (RequestError("Connection error"), "comunicação"),
    (MaxRetryError(None, "api.openai.com", "Max retries exceeded"), "retries"),
    (Exception("Unexpected error"), "inesperado"),
])
def test_proxy_network_errors(mocker, mock_env, valid_event, exception, expected_message):
    """Testa tratamento de diferentes tipos de erros de rede."""
    mock_http = MagicMock()
    mock_http.request.side_effect = exception
    mocker.patch('main.urllib3.PoolManager', return_value=mock_http)
    
    response = lambda_handler(valid_event, None)
    
    assert response["statusCode"] == 500
    error_body = json.loads(response["body"])
    assert "error" in error_body
    assert expected_message.lower() in error_body["error"].lower()

# --- Testes de Performance ---

def test_proxy_caching(mocker, mock_env, valid_event):
    """Verifica se o PoolManager é reutilizado entre chamadas."""
    mock_pool = mocker.patch('main.urllib3.PoolManager', return_value=MagicMock())
    
    # Primeira chamada
    lambda_handler(valid_event, None)
    assert mock_pool.call_count == 1
    
    # Segunda chamada - não deve criar novo PoolManager
    lambda_handler(valid_event, None)
    assert mock_pool.call_count == 1

# --- Testes de Validação de Input ---

@pytest.mark.parametrize("input_text,model,expected_status", [
    ("", "text-embedding-3-small", 400),  # Texto vazio
    ("a" * 8192, "text-embedding-3-small", 400),  # Texto muito longo
    ("texto válido", "modelo-inválido", 400),  # Modelo inválido
    ("texto válido", "", 400),  # Modelo vazio
])
def test_proxy_input_validation(mocker, mock_env, input_text, model, expected_status):
    """Testa validação de diferentes inputs."""
    mock_http = MagicMock()
    mocker.patch('main.urllib3.PoolManager', return_value=mock_http)
    
    event = {
        "body": json.dumps({
            "input": input_text,
            "model": model
        })
    }
    
    response = lambda_handler(event, None)
    assert response["statusCode"] == expected_status

# --- Testes de Logging ---

def test_proxy_logging(mocker, mock_env, valid_event, caplog):
    """Verifica se os logs apropriados são gerados."""
    mock_http = MagicMock()
    mock_http.request.return_value = MagicMock(
        status=200,
        data=b'{"data": [{"embedding": [0.1]}]}'
    )
    mocker.patch('main.urllib3.PoolManager', return_value=mock_http)
    
    with caplog.at_level(logging.INFO):
        lambda_handler(valid_event, None)
    
    # Verifica logs esperados
    assert any("Recebida requisição" in record.message for record in caplog.records)
    assert any("Resposta da OpenAI recebida" in record.message for record in caplog.records)
