"""
Ironpass — AES-256-GCM encryption and decryption.

Why AES-256-GCM:
  - AES-256: 256-bit key, computationally infeasible to brute force
  - GCM mode: Provides both encryption AND authentication
    (detects if ciphertext was tampered with)

Critical Rule #12: Fresh os.urandom(12) nonce on EVERY encrypt call.
Never reuse a nonce with the same key.
"""

import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from engine.exceptions import VaultDecryptionError, VaultEncryptionError

logger = logging.getLogger("ironpass.vault.encryption")


class VaultEncryptor:
    """
    AES-256-GCM encryption and decryption.
    Used exclusively by TokenVault — no other component calls this directly.
    """

    def __init__(self, key_manager):
        self.key_manager = key_manager

    def encrypt(self, plaintext: str, key: bytes) -> tuple[bytes, bytes]:
        """
        Encrypt plaintext string with AES-256-GCM.

        Returns (ciphertext_with_tag, nonce).

        Critical Rule #12: A fresh random 96-bit nonce is generated
        for every encryption operation. Never reused.
        """
        try:
            # Generate a fresh random 96-bit (12-byte) nonce
            nonce = os.urandom(12)

            # Create AES-GCM cipher with the 256-bit key
            aesgcm = AESGCM(key)

            # Encrypt — returns ciphertext + 16-byte authentication tag
            ciphertext = aesgcm.encrypt(
                nonce,
                plaintext.encode("utf-8"),
                None,  # No additional authenticated data
            )

            return ciphertext, nonce

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise VaultEncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: bytes, nonce: bytes, key: bytes) -> str:
        """
        Decrypt ciphertext with AES-256-GCM.

        Returns plaintext string.
        Raises VaultDecryptionError if ciphertext was tampered with
        (GCM authentication tag verification fails).

        NEVER catch VaultDecryptionError silently — always propagate and alert.
        """
        try:
            aesgcm = AESGCM(key)

            plaintext_bytes = aesgcm.decrypt(
                nonce,
                ciphertext,
                None,  # No additional authenticated data
            )

            return plaintext_bytes.decode("utf-8")

        except Exception as e:
            # This catches InvalidTag (tampered ciphertext) and other errors
            logger.critical(
                f"Decryption failed — possible tampering detected: {e}"
            )
            raise VaultDecryptionError(
                f"Decryption failed (possible tampering): {e}"
            ) from e
