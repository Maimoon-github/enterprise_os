with open('/home/maimoon-nixos/Antigravity code/Agents/agents/social_agent/agents/orchestrator.py', 'r') as f:
    text = f.read()

text = text.replace('"Analyze the user\'s latest message and return a strict JSON object with this schema:\\n"', 
'"Analyze the user\'s message and return ONLY a strict JSON object with this schema. Do not output anything else:\\n"')

text = text.replace('res = llm.invoke(messages)\n        return json.loads(res.content)',
'''res = llm.invoke(messages)
        res_text = res.content
        if res_text.startswith("```json"):
            res_text = res_text[7:-3]
        if res_text.startswith("```"):
            res_text = res_text[3:-3]
        d = json.loads(res_text.strip())
        if "mode" not in d:
             d["mode"] = "A"
        return d''')

with open('/home/maimoon-nixos/Antigravity code/Agents/agents/social_agent/agents/orchestrator.py', 'w') as f:
    f.write(text)
