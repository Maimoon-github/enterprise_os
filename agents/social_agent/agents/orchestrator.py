import json
import logging
from social_agent.agents.llm_factory import get_chat_model
from social_agent.agents.system_prompts import ORCHESTRATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def triage_intent(content: str, history=None, model_name=None) -> dict:
    llm = get_chat_model(role="evaluator", model_name_override=model_name)
    
    sys_prompt = (
        ORCHESTRATOR_SYSTEM_PROMPT + "\n\n"
        "Analyze the user's message and return ONLY a strict JSON object with this schema. Do not output anything else:\n"
        "{\n"
        "  \"mode\": \"A\" or \"B\",\n"
        "  \"response\": \"Your conversational response, strategic advice, or workflow initialization message.\",\n"
        "  \"platforms\": [\"x_twitter\", \"instagram\", \"tiktok\"] // only if Mode B, else empty array\n"
        "}"
    )
    
    messages = [("system", sys_prompt)]
    if history:
        for msg in history:
            messages.append((msg.role, msg.content))
    messages.append(("user", content))
    
    try:
        res = llm.invoke(messages)
        res_text = res.content
        if res_text.startswith("```json"):
            res_text = res_text[7:-3]
        if res_text.startswith("```"):
            res_text = res_text[3:-3]
        d = json.loads(res_text.strip())
        if "mode" not in d:
             d["mode"] = "A"
        return d
    except Exception as e:
        logger.warning(f"Intent Triaging JSON Failure: {e}")
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
        }
