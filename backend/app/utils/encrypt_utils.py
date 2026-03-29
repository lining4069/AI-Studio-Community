"""
Encryption utilities for API keys and sensitive data.
Reference: PAI-RAG project encryption approach
"""

import base64
import os

from loguru import logger

# Encryption key from environment, should be 32 bytes base64 encoded for Fernet
_ENCRYPTION_KEY: bytes | None = None


def _get_encryption_key() -> bytes | None:
    """Get or initialize the encryption key"""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        key_env = os.getenv("MODEL_API_KEY_ENCRYPTION_KEY", "")
        if key_env:
            try:
                _ENCRYPTION_KEY = base64.b64decode(key_env)
                if len(_ENCRYPTION_KEY) != 44:  # Fernet key is 44 bytes base64 encoded
                    logger.warning(
                        f"Encryption key should be 44 bytes, got {len(_ENCRYPTION_KEY)}. "
                        "Generating a new key instead."
                    )
                    _ENCRYPTION_KEY = None
            except Exception as e:
                logger.warning(f"Failed to decode encryption key: {e}")
                _ENCRYPTION_KEY = None

        if _ENCRYPTION_KEY is None:
            # Generate a new key for this process (not persistent across restarts)
            # In production, use a persistent key from KMS or environment
            logger.warning(
                "No encryption key configured. API keys will be stored as-is. "
                "Set MODEL_API_KEY_ENCRYPTION_KEY environment variable for encryption."
            )
    return _ENCRYPTION_KEY


def encrypt_api_key(plain_text: str) -> str:
    """
    Encrypt an API key using Fernet symmetric encryption.

    Args:
        plain_text: The API key to encrypt

    Returns:
        Base64 encoded encrypted string
    """
    if not plain_text:
        return plain_text

    key = _get_encryption_key()
    if key is None:
        # No encryption configured, return as-is
        return plain_text

    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(key)
        encrypted = fernet.encrypt(plain_text.encode())
        return base64.b64encode(encrypted).decode()
    except ImportError:
        logger.warning("cryptography.fernet not available, storing API key as-is")
        return plain_text
    except Exception as e:
        logger.error(f"Failed to encrypt API key: {e}")
        return plain_text


def decrypt_api_key(encrypted_text: str) -> str:
    """
    Decrypt an API key.

    Args:
        encrypted_text: Base64 encoded encrypted string

    Returns:
        Decrypted plain text API key
    """
    if not encrypted_text:
        return encrypted_text

    # Check if it's a plain API key (starts with common prefixes)
    plain_prefixes = ("sk-", "sk-prod-", "sk-dev-", "Bearer ")
    if any(encrypted_text.startswith(p) for p in plain_prefixes):
        return encrypted_text

    key = _get_encryption_key()
    if key is None:
        # No encryption configured, treat as plain text
        return encrypted_text

    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_text.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except ImportError:
        logger.warning("cryptography.fernet not available, returning as-is")
        return encrypted_text
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        return encrypted_text
