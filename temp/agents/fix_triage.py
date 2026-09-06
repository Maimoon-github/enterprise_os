with open('/home/maimoon-nixos/Antigravity code/Agents/agents/social_agent/agents/orchestrator.py', 'r') as f:
    text = f.read()

text = text.replace('''logger.error(f"Intent Triaging Error: {e}")
        query = content.lower()
        if any(w in query for w in ["post", "campaign", "launch", "draft"]):
            return {
                "mode": "B",
                "response": "Understood. Initializing multi-agent campaign workflow.",
                "platforms": ["x_twitter", "instagram"]
            }
        return {
            "mode": "A",
            "response": "I am operating in Fallback mode due to LLM timeout. How can I assist you?",
            "platforms": []
        }''', '''logger.warning(f"Intent Triaging JSON Failure: {e}")
        try:
            raw_text = res.content.strip()
            if raw_text and len(raw_text) > 10:
                return {
                    "mode": "A",
                    "response": raw_text,
                    "platforms": []
                }
        except:
            pass

        query = content.lower()
        if any(w in query for w in ["post", "campaign", "launch", "draft"]):
            return {
                "mode": "B",
                "response": "Understood. Initializing multi-agent campaign workflow.",
                "platforms": ["x_twitter", "instagram"]
            }
        return {
            "mode": "A",
            "response": "I am operating in Fallback mode due to LLM timeout. How can I assist you?",
            "platforms": []
        }''')

with open('/home/maimoon-nixos/Antigravity code/Agents/agents/social_agent/agents/orchestrator.py', 'w') as f:
    f.write(text)
