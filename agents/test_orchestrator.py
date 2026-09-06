from social_agent.agents.orchestrator import triage_intent
import json
print("Running triage...")
res1 = triage_intent("Summarize guidelines", history=[])
print(res1)
