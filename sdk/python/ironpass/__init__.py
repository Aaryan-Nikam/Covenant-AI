"""
Ironpass Python SDK.

Usage:
    from ironpass import IronpassClient, AsyncIronpassClient

    # Sync
    client = IronpassClient("http://localhost:8000")
    response = client.scan(
        target_url="https://api.openai.com/v1/chat/completions",
        content='{"messages": [...]}',
        agent_id="my-agent",
        rulesets=["pci_dss"],
    )

    # Async
    async_client = AsyncIronpassClient("http://localhost:8000")
    response = await async_client.scan(...)
"""

from ironpass.client import AsyncIronpassClient, IronpassClient
from ironpass.models import (
    BlockedError,
    RulesetInfo,
    ScanRequest,
    ScanResponse,
)

__all__ = [
    "IronpassClient",
    "AsyncIronpassClient",
    "ScanRequest",
    "ScanResponse",
    "BlockedError",
    "RulesetInfo",
]

__version__ = "0.1.0"
