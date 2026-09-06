import urllib.request
import json
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

class AvailableModelsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            url = "http://127.0.0.1:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                
            models = [m["name"] for m in data.get("models", [])]
            return Response({"models": models})
        except Exception as e:
            logger.warning(f"Could not fetch Ollama models: {e}")
            # Fallback
            return Response({"models": ["llama3.3:70b-instruct", "gpt-4"]})
