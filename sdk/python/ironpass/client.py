"""
Ironpass Python SDK — Client.

Usage:

    from ironpass import IronpassClient

    client = IronpassClient(base_url="http://localhost:8000")

    # Scan content through the compliance proxy
    response = client.scan(
        target_url="https://api.openai.com/v1/chat/completions",
        content='{"messages": [{"role": "user", "content": "process this"}]}',
        agent_id="my-agent",
        rulesets=["pci_dss", "hipaa"],
        headers={"Authorization": "Bearer sk-..."},
    )

    print(response.status)           # "passed", "sanitized", or raises BlockedError
    print(response.target_response)  # Response from OpenAI
    print(response.detections_count) # Number of detections
"""

import httpx

from ironpass.models import (
    BlockedError,
    RulesetInfo,
    ScanRequest,
    ScanResponse,
)


class IronpassClient:
    """
    Synchronous Python client for the Ironpass compliance proxy.

    Usage:
        client = IronpassClient("http://localhost:8000")
        response = client.scan(...)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def scan(
        self,
        target_url: str,
        content: str,
        agent_id: str,
        rulesets: list[str],
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> ScanResponse:
        """
        Send content through the compliance proxy.
        Returns ScanResponse on success.
        Raises BlockedError if content is blocked.
        """
        request = ScanRequest(
            target_url=target_url,
            content=content,
            agent_id=agent_id,
            rulesets=rulesets,
            headers=headers or {},
            method=method,
        )

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/proxy/scan",
                json=request.model_dump(),
            )

        if response.status_code == 403:
            detail = response.json().get("detail", {})
            raise BlockedError(
                data_type=detail.get("data_type", "unknown"),
                ruleset_id=detail.get("ruleset_id", "unknown"),
                detector_id=detail.get("detector_id", "unknown"),
                message=detail.get("error", "Request blocked"),
            )

        response.raise_for_status()
        return ScanResponse(**response.json())

    def list_rulesets(self) -> list[RulesetInfo]:
        """List all available rulesets."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/proxy/rulesets")

        response.raise_for_status()
        data = response.json()
        return [RulesetInfo(**r) for r in data.get("rulesets", [])]

    def get_ruleset(self, ruleset_id: str) -> dict:
        """Get detailed information about a specific ruleset."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/proxy/rulesets/{ruleset_id}"
            )

        response.raise_for_status()
        return response.json()

    def health(self) -> dict:
        """Check if the Ironpass server is healthy."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/health")

        response.raise_for_status()
        return response.json()


class AsyncIronpassClient:
    """
    Async Python client for the Ironpass compliance proxy.

    Usage:
        client = AsyncIronpassClient("http://localhost:8000")
        response = await client.scan(...)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def scan(
        self,
        target_url: str,
        content: str,
        agent_id: str,
        rulesets: list[str],
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> ScanResponse:
        """Async version of scan."""
        request = ScanRequest(
            target_url=target_url,
            content=content,
            agent_id=agent_id,
            rulesets=rulesets,
            headers=headers or {},
            method=method,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/proxy/scan",
                json=request.model_dump(),
            )

        if response.status_code == 403:
            detail = response.json().get("detail", {})
            raise BlockedError(
                data_type=detail.get("data_type", "unknown"),
                ruleset_id=detail.get("ruleset_id", "unknown"),
                detector_id=detail.get("detector_id", "unknown"),
                message=detail.get("error", "Request blocked"),
            )

        response.raise_for_status()
        return ScanResponse(**response.json())

    async def list_rulesets(self) -> list[RulesetInfo]:
        """Async version of list_rulesets."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/proxy/rulesets")

        response.raise_for_status()
        data = response.json()
        return [RulesetInfo(**r) for r in data.get("rulesets", [])]

    async def health(self) -> dict:
        """Async health check."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/health")

        response.raise_for_status()
        return response.json()
