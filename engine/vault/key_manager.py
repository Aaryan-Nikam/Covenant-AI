"""
Ironpass — Key Manager.

Fetches encryption keys from external key management systems.
Keys NEVER stored in the application database (Critical Rule #3).
Keys NEVER cached longer than the current operation.

Supports three backends (configured via KEY_BACKEND env var):
  1. HashiCorp Vault (self-hosted): KEY_BACKEND=hashicorp
  2. AWS KMS: KEY_BACKEND=aws_kms
  3. Local (development ONLY): KEY_BACKEND=local

Key versioning:
  - Keys are versioned (v1, v2, v3...)
  - Old keys kept for decryption of older tokens
  - New tokens always encrypted with current key version
"""

import logging

from engine.config import get_settings
from engine.exceptions import KeyManagementError

logger = logging.getLogger("ironpass.vault.key_manager")


import time
from threading import Lock

class KeyManager:
    """
    Fetches encryption keys from the configured backend.
    Never stores keys in the application DB.
    Never caches keys longer than the TTL (5 minutes by default).
    """

    _cache: dict[str, tuple[bytes, str, float]] = {}  # key_version -> (key_bytes, key_version, timestamp)
    _cache_lock = Lock()
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self):
        self.settings = get_settings()
        self.backend = self.settings.key_backend
        self._current_version = "v1"

        if self.backend == "local":
            if not self.settings.local_vault_key:
                raise KeyManagementError(
                    "KEY_BACKEND=local requires LOCAL_VAULT_KEY to be set"
                )
            logger.warning(
                "Using LOCAL key backend — for development only, "
                "never use in production!"
            )
        elif self.backend == "hashicorp":
            if not self.settings.hashicorp_vault_url:
                raise KeyManagementError(
                    "KEY_BACKEND=hashicorp requires HASHICORP_VAULT_URL"
                )
            if not self.settings.hashicorp_vault_token:
                raise KeyManagementError(
                    "KEY_BACKEND=hashicorp requires HASHICORP_VAULT_TOKEN"
                )
        elif self.backend == "aws_kms":
            if not self.settings.aws_kms_key_id:
                raise KeyManagementError(
                    "KEY_BACKEND=aws_kms requires AWS_KMS_KEY_ID"
                )
        else:
            raise KeyManagementError(
                f"Unknown KEY_BACKEND: '{self.backend}'. "
                f"Must be 'local', 'hashicorp', or 'aws_kms'"
            )

    async def get_current_key(self) -> tuple[bytes, str]:
        """
        Returns (key_bytes, key_version) for the current encryption key.
        Used when encrypting new values.
        """
        if self.backend == "local":
            return self._get_local_key(), self._current_version
        elif self.backend == "hashicorp":
            return await self._get_hashicorp_key()
        elif self.backend == "aws_kms":
            return await self._get_aws_kms_key()
        else:
            raise KeyManagementError(f"Unknown backend: {self.backend}")

    async def get_key_by_version(self, version: str) -> bytes:
        """
        Get a key by version. Used for decrypting tokens encrypted
        with older key versions during key rotation.
        """
        if self.backend == "local":
            # Local backend only has one key version
            return self._get_local_key()
        elif self.backend == "hashicorp":
            key, _ = await self._get_hashicorp_key(version=version)
            return key
        elif self.backend == "aws_kms":
            key, _ = await self._get_aws_kms_key(version=version)
            return key
        else:
            raise KeyManagementError(f"Unknown backend: {self.backend}")

    def _get_local_key(self) -> bytes:
        """
        Local development backend — reads key from LOCAL_VAULT_KEY env var.
        The env var is a 64-char hex string → 32 bytes (256 bits).
        """
        hex_key = self.settings.local_vault_key
        try:
            key_bytes = bytes.fromhex(hex_key)
            if len(key_bytes) != 32:
                raise KeyManagementError(
                    f"LOCAL_VAULT_KEY must be 64 hex chars (32 bytes), "
                    f"got {len(key_bytes)} bytes"
                )
            return key_bytes
        except ValueError as e:
            raise KeyManagementError(
                f"LOCAL_VAULT_KEY is not valid hex: {e}"
            )

    async def _get_hashicorp_key(
        self, version: str | None = None
    ) -> tuple[bytes, str]:
        """
        Fetch encryption key from HashiCorp Vault (KV-v2 secrets engine).

        Reads from: secret/data/ironpass/encryption-key
        Expected format: key stored as 64-char hex string in the
        "key" field (or "key_v2", "key_v3" for versioned keys).

        Vault API docs: GET /v1/secret/data/{path}
        """
        import httpx

        vault_url = self.settings.hashicorp_vault_url.rstrip("/")
        vault_token = self.settings.hashicorp_vault_token
        key_version = version or self._current_version

        # Check cache under lock
        with KeyManager._cache_lock:
            cached = KeyManager._cache.get(key_version)
            if cached:
                cached_bytes, cached_ver, timestamp = cached
                if time.time() - timestamp < KeyManager.CACHE_TTL_SECONDS:
                    return cached_bytes, cached_ver

        # Map version to field name: v1 → "key", v2 → "key_v2", etc.
        field_name = "key" if key_version == "v1" else f"key_{key_version}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{vault_url}/v1/secret/data/ironpass/encryption-key",
                    headers={"X-Vault-Token": vault_token},
                )

                if response.status_code == 403:
                    raise KeyManagementError(
                        "HashiCorp Vault: permission denied. "
                        "Check HASHICORP_VAULT_TOKEN has read access to "
                        "secret/data/ironpass/encryption-key"
                    )
                elif response.status_code == 404:
                    raise KeyManagementError(
                        "HashiCorp Vault: secret not found at "
                        "secret/data/ironpass/encryption-key. "
                        "Create with: vault kv put secret/ironpass/encryption-key "
                        "key=<64-hex-chars>"
                    )
                elif response.status_code != 200:
                    raise KeyManagementError(
                        f"HashiCorp Vault: unexpected status {response.status_code}"
                    )

                data = response.json()
                secret_data = data.get("data", {}).get("data", {})

                if field_name not in secret_data:
                    raise KeyManagementError(
                        f"HashiCorp Vault: field '{field_name}' not found "
                        f"in secret/ironpass/encryption-key. "
                        f"Available fields: {list(secret_data.keys())}"
                    )

                hex_key = secret_data[field_name]

                # Validate key format
                try:
                    key_bytes = bytes.fromhex(hex_key)
                except ValueError:
                    raise KeyManagementError(
                        f"HashiCorp Vault: field '{field_name}' is not valid hex"
                    )

                if len(key_bytes) != 32:
                    raise KeyManagementError(
                        f"HashiCorp Vault: key must be 32 bytes (64 hex chars), "
                        f"got {len(key_bytes)} bytes"
                    )

                logger.debug(
                    f"HashiCorp Vault: fetched key version={key_version}"
                )
                
                with KeyManager._cache_lock:
                    KeyManager._cache[key_version] = (key_bytes, key_version, time.time())
                
                return key_bytes, key_version

        except httpx.ConnectError:
            raise KeyManagementError(
                f"HashiCorp Vault unreachable at {vault_url}. "
                f"Is the Vault server running?"
            )
        except httpx.TimeoutException:
            raise KeyManagementError(
                f"HashiCorp Vault timeout at {vault_url}"
            )
        except KeyManagementError:
            raise
        except Exception as e:
            raise KeyManagementError(
                f"HashiCorp Vault error: {e}"
            )

    async def _get_aws_kms_key(
        self, version: str | None = None
    ) -> tuple[bytes, str]:
        """
        Fetch data key from AWS KMS.
        Since we cannot store keys in the DB (Rule #3), and KMS doesn't
        store secrets, we store the KMS-encrypted data key ciphertext
        in a local file on the EC2 instance for the given version.
        """
        import boto3
        import asyncio
        import os
        from botocore.exceptions import ClientError
        from engine.exceptions import KeyManagementError

        key_version = version or self._current_version

        # Check cache under lock
        with KeyManager._cache_lock:
            cached = KeyManager._cache.get(key_version)
            if cached:
                cached_bytes, cached_ver, timestamp = cached
                if time.time() - timestamp < KeyManager.CACHE_TTL_SECONDS:
                    return cached_bytes, cached_ver

        kms_key_id = self.settings.aws_kms_key_id
        region = getattr(self.settings, "aws_region", "us-east-1")
        
        # Path to store the encrypted data key for this version
        key_file_path = f".ironpass_kms_{key_version}.enc"

        def _fetch_or_generate():
            client = boto3.client("kms", region_name=region)
            
            # If we already generated a key for this version, decrypt it
            if os.path.exists(key_file_path):
                with open(key_file_path, "rb") as f:
                    ciphertext = f.read()
                try:
                    response = client.decrypt(
                        CiphertextBlob=ciphertext,
                        KeyId=kms_key_id
                    )
                    logger.debug(f"AWS KMS: decrypted data key for version={key_version}")
                    return response["Plaintext"], key_version
                except ClientError as e:
                    raise KeyManagementError(f"AWS KMS decryption failed: {e}")

            # Otherwise, generate a new data key
            try:
                response = client.generate_data_key(
                    KeyId=kms_key_id,
                    NumberOfBytes=32
                )
                plaintext = response["Plaintext"]
                ciphertext = response["CiphertextBlob"]
                
                # Save ciphertext to disk so other workers/restarts can use the same key
                with open(key_file_path, "wb") as f:
                    f.write(ciphertext)
                    
                logger.info(f"AWS KMS: generated new data key for version={key_version}")
                return plaintext, key_version
                
            except ClientError as e:
                raise KeyManagementError(f"AWS KMS generate_data_key failed: {e}")

        # Run boto3 calls in an executor since they are synchronous HTTP requests
        loop = asyncio.get_running_loop()
        try:
            key_bytes, key_ver = await loop.run_in_executor(None, _fetch_or_generate)
            
            with KeyManager._cache_lock:
                KeyManager._cache[key_ver] = (key_bytes, key_ver, time.time())
                
            return key_bytes, key_ver
        except Exception as e:
            raise KeyManagementError(f"AWS KMS error: {e}")
