import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from social_agent.agents.orchestrator import triage_intent
print(triage_intent("give me a demo by listing the directory mcp_tools!"))
