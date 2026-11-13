"""Checks the fake LLM against the backend's real agno code path.

The e2e suite only works if agno accepts what the fake returns. This runs the same
calls the backend makes — the AI-setup key check and a ChatAgent-style structured
reply — through agno against a running fake, so an agno upgrade that changes the
request or response shape fails here with a clear message instead of as flaky e2e
tests. CI runs it right after the stack starts.

    cd backend && PYTHONPATH=. ENV_FILE=../e2e/.env.e2e NO_ENTERPRISE=1 \\
        python ../e2e/services/fake-llm/contract_check.py [base_url]
"""

import asyncio
import json
import sys
import urllib.request

from agno.agent import Agent

from app.models.schemas.chat import ChatResponse
from app.utils.agno_utils import create_model, test_model_api_key

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:14010/v1"
CONTROL = BASE_URL.removesuffix("/v1")
SCENARIO = "contract-check"


def put_scenario() -> None:
    spec = {"rules": [
        {"match": {"source": "human", "flags": "i"},
         "reply": {"message": "Connecting you.", "fields": {"transfer_to_human": True}}},
        {"reply": {"message": "Happy to help!"}},
    ]}
    req = urllib.request.Request(f"{CONTROL}/__scenarios/{SCENARIO}", data=json.dumps(spec).encode(),
                                 method="PUT", headers={"content-type": "application/json"})
    urllib.request.urlopen(req).read()


async def main() -> int:
    put_scenario()
    assert await test_model_api_key("e2e-key", "OPENAI_COMPATIBLE", "e2e-fake", base_url=BASE_URL), \
        "AI-setup key check failed against the fake"

    model = create_model("OPENAI_COMPATIBLE", "e2e-key", "e2e-fake", max_tokens=1000, base_url=BASE_URL)
    agent = Agent(model=model, instructions=f"Contract check. [[e2e:{SCENARIO}]]",
                  response_model=ChatResponse, structured_outputs=True, system_message_role="system")

    handover = (await agent.arun("I want a human")).content
    assert isinstance(handover, ChatResponse), f"structured reply not parsed: {handover!r}"
    assert handover.transfer_to_human is True and handover.message == "Connecting you.", handover

    plain = (await agent.arun("hello")).content
    assert plain.transfer_to_human is False and plain.message == "Happy to help!", plain

    print("fake LLM contract OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
