from authlib.integrations.httpx_client import AsyncOAuth2Client

class PlatformOAuthManager:
    @staticmethod
    def get_oauth_client(platform: str, client_id: str, client_secret: str) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(client_id=client_id, client_secret=client_secret)
