"""
Encryption utilities for API keys and sensitive data.

Design goals:
- 支持 Fernet 标准加密
- 支持任意字符串 key（自动派生）
- 避免明文 fallback（生产安全）
- 支持 key 校验
- 兼容旧数据（可选）
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from loguru import logger

# =========================
# Key Management
# =========================


@lru_cache
def _get_encryption_key() -> bytes | None:
    """
    获取 Fernet 可用 key（32 bytes urlsafe base64）

    支持两种输入：
    1. 标准 Fernet key（44字符）
    2. 任意字符串（自动派生）
    """
    from app.core.settings import get_settings

    key_env = get_settings().MODEL_API_KEY_ENCRYPTION_KEY

    if not key_env:
        logger.warning("No encryption key configured")
        return None

    key_env = key_env.strip()

    # ✅ 情况1：标准 Fernet key（推荐）
    if len(key_env) == 44:
        try:
            key_bytes = key_env.encode()
            from cryptography.fernet import Fernet

            Fernet(key_bytes)  # 校验合法性
            return key_bytes
        except Exception:
            logger.warning("Invalid Fernet key format, fallback to KDF")

    # ✅ 情况2：任意字符串 → 派生 Fernet key（更灵活）
    try:
        logger.info("Deriving Fernet key from provided secret")

        # 使用 SHA256 派生 32 bytes，再转 base64
        digest = hashlib.sha256(key_env.encode()).digest()
        derived_key = base64.urlsafe_b64encode(digest)

        return derived_key
    except Exception as e:
        logger.error(f"Failed to derive encryption key: {e}")
        return None


# =========================
# Encryption
# =========================


def encrypt_api_key(plain_text: str) -> str:
    """
    加密 API Key

    返回：base64(encoded Fernet token)
    """
    if not plain_text:
        return plain_text

    key = _get_encryption_key()
    if key is None:
        # ⚠️ 不再 silently 明文存储
        raise RuntimeError("Encryption key not configured")

    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(key)
        token = fernet.encrypt(plain_text.encode())

        # 二次 base64（保证 DB 可安全存储）
        return base64.urlsafe_b64encode(token).decode()

    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


# =========================
# Decryption
# =========================


def decrypt_api_key(encrypted_text: str) -> str:
    """
    解密 API Key
    """
    if not encrypted_text:
        return encrypted_text

    # ✅ 兼容旧数据（明文）
    if _looks_like_plain_text(encrypted_text):
        return encrypted_text

    key = _get_encryption_key()
    if key is None:
        raise RuntimeError("Encryption key not configured")

    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(key)

        token = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted = fernet.decrypt(token)

        return decrypted.decode()

    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


# =========================
# Helpers
# =========================


def _looks_like_plain_text(text: str) -> bool:
    """
    判断是否是未加密的 API Key（用于兼容历史数据）
    """
    prefixes = ("sk-", "sk-prod-", "sk-dev-", "Bearer ")
    return any(text.startswith(p) for p in prefixes)
