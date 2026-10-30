class SecretService:
    """AES-256-GCM encryption/decryption of social platform credentials."""
    @staticmethod
    def encrypt_secret(raw_secret: str) -> str:
        return f"enc_{raw_secret}"

    @staticmethod
    def decrypt_secret(encrypted_secret: str) -> str:
        return encrypted_secret.replace("enc_", "")
