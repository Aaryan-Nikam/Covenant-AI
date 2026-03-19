"""
Ironpass — Token Vault.

Single interface for all vault operations.
No other component calls encryption directly.
Encrypts every value with AES-256-GCM before writing to DB.
Keys never stored in the application database (Critical Rule #3).

Architecture doc reference: Component 4 — Token Vault.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.config import get_settings
from engine.exceptions import (
    VaultError,
    VaultTokenExpiredError,
    VaultTokenInvalidatedError,
    VaultUnauthorizedError,
)
from engine.vault.encryption import VaultEncryptor
from engine.vault.key_manager import KeyManager
from engine.vault.models import VaultToken

logger = logging.getLogger("ironpass.vault")


class TokenVault:
    """
    Single interface for all vault operations.
    No other component calls encryption directly.
    """

    def __init__(self, db_session: AsyncSession, key_manager: KeyManager):
        self.db = db_session
        self.key_manager = key_manager
        self.encryptor = VaultEncryptor(key_manager)

    async def store(
        self,
        token: str,
        plaintext: str,
        data_type: str,
        agent_id: str,
        ttl_hours: int | None = None,
    ) -> bool:
        """
        Encrypts plaintext and stores with token as key.
        Returns True on success.

        Flow:
        1. Fetch current encryption key from key manager
        2. Encrypt plaintext with AES-256-GCM (fresh nonce)
        3. Store ciphertext, nonce, and metadata in DB
        """
        settings = get_settings()
        ttl = ttl_hours or settings.vault_token_ttl_hours

        try:
            # Get current encryption key
            key, key_version = await self.key_manager.get_current_key()

            # Encrypt the plaintext value
            ciphertext, nonce = self.encryptor.encrypt(plaintext, key)

            # Create the vault token record
            now = datetime.now(timezone.utc)
            vault_token = VaultToken(
                token=token,
                ciphertext=ciphertext,
                nonce=nonce,
                data_type=data_type,
                agent_id=agent_id,
                created_at=now,
                expires_at=now + timedelta(hours=ttl),
                key_version=key_version,
            )

            self.db.add(vault_token)
            await self.db.flush()

            logger.debug(
                f"Stored token: {token} (type={data_type}, agent={agent_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store token {token}: {e}")
            raise VaultError(f"Failed to store token: {e}") from e

    async def retrieve(
        self,
        token: str,
        requesting_agent_id: str,
    ) -> str | None:
        """
        Verifies agent_id matches token owner.
        Checks token not expired or invalidated.
        Decrypts and returns plaintext.
        Returns None if not found.
        Logs every retrieval attempt (success and failure).
        """
        try:
            # Fetch token from DB
            result = await self.db.execute(
                select(VaultToken).where(VaultToken.token == token)
            )
            vault_token = result.scalar_one_or_none()

            if vault_token is None:
                logger.warning(f"Token not found: {token}")
                return None

            # Authorization check — agent must match
            if vault_token.agent_id != requesting_agent_id:
                logger.warning(
                    f"Unauthorized retrieval attempt: token={token}, "
                    f"owner={vault_token.agent_id}, "
                    f"requester={requesting_agent_id}"
                )
                raise VaultUnauthorizedError(
                    f"Agent '{requesting_agent_id}' is not authorized "
                    f"to access token '{token}'"
                )

            # Check if invalidated (GDPR erasure)
            if vault_token.invalidated_at is not None:
                logger.info(f"Token invalidated: {token}")
                raise VaultTokenInvalidatedError(token)

            # Check if expired
            now = datetime.now(timezone.utc)
            if vault_token.expires_at.tzinfo is None:
                expires = vault_token.expires_at.replace(tzinfo=timezone.utc)
            else:
                expires = vault_token.expires_at

            if now > expires:
                logger.info(f"Token expired: {token}")
                raise VaultTokenExpiredError(token)

            # Decrypt
            key = await self.key_manager.get_key_by_version(
                vault_token.key_version
            )
            plaintext = self.encryptor.decrypt(
                vault_token.ciphertext, vault_token.nonce, key
            )

            logger.debug(f"Retrieved token: {token}")
            return plaintext

        except (VaultUnauthorizedError, VaultTokenExpiredError, VaultTokenInvalidatedError):
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve token {token}: {e}")
            raise VaultError(f"Failed to retrieve token: {e}") from e

    async def invalidate(self, token: str, reason: str) -> bool:
        """
        Sets invalidated_at. Token cannot be retrieved after this.
        Used for GDPR right-to-erasure requests.
        """
        try:
            result = await self.db.execute(
                select(VaultToken).where(VaultToken.token == token)
            )
            vault_token = result.scalar_one_or_none()

            if vault_token is None:
                logger.warning(f"Cannot invalidate — token not found: {token}")
                return False

            vault_token.invalidated_at = datetime.now(timezone.utc)
            await self.db.flush()

            logger.info(
                f"Token invalidated: {token} (reason: {reason})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate token {token}: {e}")
            raise VaultError(f"Failed to invalidate token: {e}") from e

    async def cleanup_expired(self) -> int:
        """
        Deletes expired tokens.
        Run as scheduled job every 24 hours.
        Returns count of deleted tokens.
        """
        from sqlalchemy import delete

        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                delete(VaultToken).where(VaultToken.expires_at < now)
            )
            count = result.rowcount
            await self.db.flush()

            if count > 0:
                logger.info(f"Cleaned up {count} expired tokens")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            raise VaultError(f"Cleanup failed: {e}") from e
