import json
import os
from unittest.mock import MagicMock

# Adiciona o diretório src ao sys.path para permitir importações locais
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / 'src' / 'openai_embedding_proxy'))

# Importa o handler principal da função Lambda
from main import lambda_handler

# --- Testes para a Função Lambda: openai_embedding_proxy ---

def test_proxy_success_path(mocker):
    """
    Testa o caminho feliz (happy path) da função de proxy.
    Verifica se a função lê a chave de API, faz a requisição para a OpenAI
    e retorna a resposta corretamente.
    """
    # Mock das variáveis de ambiente
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})

    # Mock do urllib3.PoolManager
    mock_pool = MagicMock()
    mock_http = MagicMock()
    mock_http.request.return_value = MagicMock(
        status=200,
        data=json.dumps({"embedding": [0.1, 0.2, 0.3]})
    )
    mock_pool.return_value = mock_http
    mocker.patch('main.urllib3.PoolManager', mock_pool)

    # Payload de evento de entrada para a Lambda
    event = {
        "body": json.dumps({
            "input": "test input",
            "model": "text-embedding-3-small"
        })
    }

    # Execução da função
    response = lambda_handler(event, None)

    # Asserts
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"embedding": [0.1, 0.2, 0.3]}

    # Verifica se a requisição foi feita com os parâmetros corretos
    mock_http.request.assert_called_once_with(
        "POST",
        "https://api.openai.com/v1/embeddings",
        body=event["body"],
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test-key-12345",
        },
        timeout=25
    )


def test_proxy_missing_api_key(mocker):
    """
    Testa o comportamento da função quando a variável de ambiente OPENAI_API_KEY não está definida.
    A função deve retornar um erro 500.
    """
    # Garante que a variável de ambiente não está definida
    mocker.patch.dict(os.environ, clear=True)

    # Payload de evento (não deve ser processado)
    event = {"body": "{}"}

    # Execução e assert
    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "OPENAI_API_KEY" in body["error"]


def test_proxy_openai_api_error(mocker):
    """
    Testa o comportamento da função quando a API da OpenAI retorna um erro (ex: 401 Unauthorized).
    A função deve propagar o status de erro e a resposta.
    """
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "invalid-key"})

    # Mock do urllib3 para simular um erro da API
    mock_pool = MagicMock()
    mock_http = MagicMock()
    error_response_body = json.dumps({"error": {"message": "Incorrect API key"}})
    mock_http.request.return_value = MagicMock(
        status=401,
        data=error_response_body
    )
    mock_pool.return_value = mock_http
    mocker.patch('main.urllib3.PoolManager', mock_pool)

    event = {"body": json.dumps({"input": "test"})}

    # Execução e assert
    response = lambda_handler(event, None)
    assert response["statusCode"] == 401
    assert response["body"] == error_response_body


def test_proxy_network_error(mocker):
    """
    Testa o comportamento da função em caso de erro de rede (ex: timeout).
    A função deve capturar a exceção e retornar um erro 500 genérico.
    """
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})

    # Mock do urllib3 para levantar uma exceção
    mock_pool = MagicMock()
    mock_http = MagicMock()
    mock_http.request.side_effect = Exception("Network timeout")
    mock_pool.return_value = mock_http
    mocker.patch('main.urllib3.PoolManager', mock_pool)

    event = {"body": json.dumps({"input": "test"})}

    # Execução e assert
    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "Network timeout" in body["error"]
