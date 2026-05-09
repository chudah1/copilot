from cryptography.fernet import Fernet
import base64

from app.config import settings


def _get_fernet() -> Fernet:
    # Fernet requires a 32-byte key, url-safe base64-encoded
    raw_key = settings.encryption_key.encode()[:32].ljust(32, b"\0")
    key = base64.urlsafe_b64encode(raw_key)
    return Fernet(key)


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
