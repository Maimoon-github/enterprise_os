from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth2Client


class PlatformOAuthManager:
    @staticmethod
    def get_oauth_client(
        platform: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str | None = None,
        scope: str | None = None,
        **kwargs: Any,
    ) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            **kwargs,
        )
