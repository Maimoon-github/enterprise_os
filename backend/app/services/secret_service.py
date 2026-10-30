import hashlib
import os

from app.core.config import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretService:
    """Zero-trust AES-256-GCM encryption/decryption of social platform credentials and OAuth secrets.

    Ensures agents and LLM worker contexts never receive raw tokens or master API keys.
    """

    @classmethod
    def _get_aes_key(cls) -> bytes:
        """Derive deterministic 256-bit key from application SECRET_KEY via SHA-256."""
        return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()

    @classmethod
    def encrypt_secret(cls, raw_secret: str) -> str:
        """Encrypt plaintext credential using AES-256-GCM with a 96-bit random nonce."""
        if not raw_secret:
            return ""
        key = cls._get_aes_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, raw_secret.encode("utf-8"), None)
        # Store nonce + ciphertext as hex
        return f"aes256gcm_{nonce.hex()}:{ciphertext.hex()}"

    @classmethod
    def decrypt_secret(cls, encrypted_secret: str) -> str:
        """Decrypt AES-256-GCM ciphertext using the derived master key."""
        if not encrypted_secret:
            return ""
        if not encrypted_secret.startswith("aes256gcm_"):
            # Backward-compatible fallback for legacy mock tokens
            if encrypted_secret.startswith("enc_"):
                return encrypted_secret.replace("enc_", "", 1)
            return encrypted_secret

        try:
            payload = encrypted_secret.replace("aes256gcm_", "", 1)
            nonce_hex, ct_hex = payload.split(":", 1)
            nonce = bytes.fromhex(nonce_hex)
            ciphertext = bytes.fromhex(ct_hex)
            key = cls._get_aes_key()
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")
        except Exception as exc:
            raise ValueError(f"Failed to decrypt credential: {exc}") from exc

    encrypt = encrypt_secret
    decrypt = decrypt_secret


secret_service = SecretService()
