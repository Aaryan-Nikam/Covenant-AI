"""
Forwards sanitized requests to the real OpenAI API.
Handles timeouts, retries, and error translation.

Rules:
- Use httpx AsyncClient — never requests (blocking)
- 30 second timeout on all requests
- Retry ONCE on 429 (rate limit) after 1 second delay
- Never retry on 4xx errors (except 429) — they are agent errors
- Never retry on 5xx more than once — OpenAI problem, not ours
- Never expose OpenAI error details directly — translate them
- Always include latency in the return value
- X-OpenAI-Key is used here and only here — never stored, never logged in full
"""

import httpx
import asyncio
import time
from dataclasses import dataclass


OPENAI_BASE_URL = "https://api.openai.com"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES_ON_RATE_LIMIT = 1
RATE_LIMIT_RETRY_DELAY_SECONDS = 1


@dataclass
class ForwardResult:
    success: bool
    response_body: dict | None
    status_code: int
    latency_ms: int
    error_type: str | None        # None on success
    error_message: str | None     # None on success


class OpenAIForwarder:

    async def forward(
        self,
        path: str,                  # e.g. "/v1/chat/completions"
        payload: dict,              # Sanitized OpenAI payload
        openai_api_key: str,        # Customer's OpenAI key — use, never store
        additional_headers: dict = {},
    ) -> ForwardResult:
        """
        Forwards sanitized payload to OpenAI.
        Returns ForwardResult with response or structured error.
        """
        url = f"{OPENAI_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
            **additional_headers
        }

        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await self._send_with_retry(
                    client=client,
                    url=url,
                    payload=payload,
                    headers=headers,
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)

                return ForwardResult(
                    success=True,
                    response_body=response.json(),
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error_type=None,
                    error_message=None,
                )

            except httpx.TimeoutException:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=504,
                    latency_ms=latency_ms,
                    error_type="upstream_timeout",
                    error_message="AI provider did not respond in time",
                )

            except httpx.HTTPStatusError as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=e.response.status_code,
                    latency_ms=latency_ms,
                    error_type="upstream_error",
                    error_message="AI provider returned an error",
                )

            except Exception as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=500,
                    latency_ms=latency_ms,
                    error_type="internal_error",
                    error_message="Unexpected error forwarding request",
                )

    async def _send_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        headers: dict,
    ) -> httpx.Response:
        """
        Sends request. Retries once on 429.
        Raises httpx.HTTPStatusError on non-retryable errors.
        """
        for attempt in range(MAX_RETRIES_ON_RATE_LIMIT + 1):
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429 and attempt == 0:
                # Rate limited — wait and retry once
                await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
                continue

            response.raise_for_status()
            return response

        # Should not reach here
        response.raise_for_status()
        return response
