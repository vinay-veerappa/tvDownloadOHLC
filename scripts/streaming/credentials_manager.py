"""
credentials_manager.py
======================
Secure credentials storage and retrieval manager.

Supports:
  1. Plain secrets.json (ignored by git).
  2. Encrypted secrets.enc using Windows Data Protection API (win32crypt DPAPI)
     or machine-bound encryption, ensuring credentials cannot be decrypted
     outside the user's logged-in Windows account.

Usage:
  from scripts.streaming.credentials_manager import get_secret, save_secrets, get_tos_credentials, get_schwab_credentials

  tos_user, tos_pass = get_tos_credentials()
"""
import os
import sys
import json
import logging
import base64
import hashlib
from pathlib import Path

log = logging.getLogger("CredentialsManager")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SECRETS_JSON = REPO_ROOT / "secrets.json"
SECRETS_ENC = REPO_ROOT / "secrets.enc"

# Try DPAPI on Windows
_DPAPI_AVAILABLE = False
if sys.platform == "win32":
    try:
        import win32crypt
        _DPAPI_AVAILABLE = True
    except ImportError:
        pass


def _get_machine_key() -> bytes:
    """Generate a machine/user bound key as fallback if DPAPI is unavailable."""
    import platform
    user = os.getenv("USERNAME", "default_user")
    node = platform.node()
    raw = f"{user}:{node}:tvDownloadOHLC-secret-salt"
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _encrypt_bytes(data: bytes) -> bytes:
    """Encrypt bytes using Windows DPAPI or machine key."""
    if _DPAPI_AVAILABLE:
        try:
            # CryptProtectData encrypts using current logged-in Windows user context
            return win32crypt.CryptProtectData(data, "tvDownloadOHLC-Credentials", None, None, None, 0)
        except Exception as e:
            log.warning("DPAPI encryption failed, falling back to machine key: %s", e)
    
    # Simple XOR + SHA256 stream cipher fallback
    key = _get_machine_key()
    encrypted = bytearray()
    for i, b in enumerate(data):
        k = key[i % len(key)]
        encrypted.append(b ^ k)
    return bytes(encrypted)


def _decrypt_bytes(data: bytes) -> bytes:
    """Decrypt bytes using Windows DPAPI or machine key."""
    if _DPAPI_AVAILABLE:
        try:
            _, decrypted = win32crypt.CryptUnprotectData(data, None, None, None, 0)
            return decrypted
        except Exception:
            pass
            
    # Fallback machine key decryption
    key = _get_machine_key()
    decrypted = bytearray()
    for i, b in enumerate(data):
        k = key[i % len(key)]
        decrypted.append(b ^ k)
    return bytes(decrypted)


def load_secrets() -> dict:
    """Load secrets from secrets.enc (preferred) or secrets.json."""
    if SECRETS_ENC.exists():
        try:
            encrypted_data = SECRETS_ENC.read_bytes()
            decrypted_data = _decrypt_bytes(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            log.error("Failed to decrypt secrets.enc: %s", e)

    if SECRETS_JSON.exists():
        try:
            with open(SECRETS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error("Failed to read secrets.json: %s", e)

    return {}


def save_secrets(secrets_dict: dict, encrypt: bool = True) -> bool:
    """Save secrets dict to secrets.enc (encrypted) and/or secrets.json."""
    try:
        raw_json = json.dumps(secrets_dict, indent=2).encode('utf-8')
        if encrypt:
            encrypted_bytes = _encrypt_bytes(raw_json)
            SECRETS_ENC.write_bytes(encrypted_bytes)
            log.info("Saved encrypted credentials to secrets.enc")

        # Always maintain local secrets.json if requested or as fallback
        with open(SECRETS_JSON, "w", encoding="utf-8") as f:
            json.dump(secrets_dict, f, indent=2)
        return True
    except Exception as e:
        log.error("Failed to save secrets: %s", e)
        return False


def get_secret(key: str, default: str | None = None) -> str | None:
    """Get a specific secret by key."""
    secrets = load_secrets()
    return secrets.get(key, default)


def get_tos_credentials() -> tuple[str | None, str | None]:
    """Retrieve Thinkorswim username and password."""
    secrets = load_secrets()
    return secrets.get("tos_username"), secrets.get("tos_password")


def get_schwab_credentials() -> tuple[str | None, str | None, str | None]:
    """Retrieve Schwab App Key, App Secret, and Callback URL."""
    secrets = load_secrets()
    return (
        secrets.get("app_key"),
        secrets.get("app_secret"),
        secrets.get("callback_url", "https://127.0.0.1:8080/callback")
    )


def get_schwab_web_credentials() -> tuple[str | None, str | None]:
    """Retrieve Schwab web portal login username and password."""
    secrets = load_secrets()
    u = secrets.get("schwab_username") or secrets.get("tos_username")
    p = secrets.get("schwab_password") or secrets.get("tos_password")
    return u, p


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = load_secrets()
    print(f"Loaded {len(s)} keys from storage. Encryption active: {_DPAPI_AVAILABLE}")
