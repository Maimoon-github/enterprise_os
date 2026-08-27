import logging
logging.basicConfig(level=logging.ERROR)
from social_agent.agents.llm_factory import get_chat_model
from social_agent.agents.system_prompts import ORCHESTRATOR_SYSTEM_PROMPT

llm = get_chat_model(role='evaluator', model_name_override='llama3.2:3b')
sys_prompt = (
    ORCHESTRATOR_SYSTEM_PROMPT + "\n\n"
    "Analyze the user's message and return ONLY a strict JSON object with this schema. Do not output anything else:\n"
    "{\n"
    "  \"mode\": \"A\" or \"B\",\n"
    "  \"response\": \"Your conversational response, strategic advice, or workflow initialization message.\",\n"
    "  \"platforms\": [\"x_twitter\", \"instagram\", \"tiktok\"] // only if Mode B, else empty array\n"
    "}"
)
messages = [("system", sys_prompt), ("user", "could you give me your persona?")]
res = llm.invoke(messages)
print("==== RAW LLM RES ====")
print(repr(res.content))
