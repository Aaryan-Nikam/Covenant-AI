import pytest
import httpx
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from engine.proxy.forwarder import OpenAIForwarder, ForwardResult

@pytest.fixture
def forwarder():
    return OpenAIForwarder()

@pytest.mark.asyncio
async def test_successful_forward(forwarder):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "chat-xxx"}
        mock_post.return_value = mock_resp

        result = await forwarder.forward(
            "/v1/chat/completions",
            {"model": "gpt-4"},
            "sk-fake"
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.response_body == {"id": "chat-xxx"}
        assert result.error_type is None
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_timeout_forward(forwarder):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")

        result = await forwarder.forward(
            "/v1/chat/completions",
            {"model": "gpt-4"},
            "sk-fake"
        )

        assert result.success is False
        assert result.status_code == 504
        assert result.error_type == "upstream_timeout"

@pytest.mark.asyncio
async def test_429_retry_then_success(forwarder):
    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
         
        # First call returns 429, second returns 200
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"id": "success"}

        mock_post.side_effect = [mock_resp_429, mock_resp_200]

        result = await forwarder.forward(
            "/v1/chat/completions",
            {"model": "gpt-4"},
            "sk-fake"
        )

        assert result.success is True
        assert result.status_code == 200
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()  # Should have waited after 429

@pytest.mark.asyncio
async def test_500_error_no_retry(forwarder):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        
        # raise_for_status will raise HTTPStatusError
        error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_resp_500)
        mock_resp_500.raise_for_status.side_effect = error
        
        mock_post.return_value = mock_resp_500

        result = await forwarder.forward(
            "/v1/chat/completions",
            {"model": "gpt-4"},
            "sk-fake"
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.error_type == "upstream_error"
        assert mock_post.call_count == 1  # No retry on 500
