import os
import sys
import time
import requests
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.schemas import RecoveryDecision

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

FAKE_GE_REPORT = """
Great Expectations Validation Failure Report:
- Check: order_id unique
- Status: FAILED
- Details: 16 duplicate order_id values found in raw_orders table.
- Sample failing values: ['FAKE-DUPE-001', 'FAKE-DUPE-001']
"""

PROMPT = f"""You are a DataOps recovery agent. Analyze this Great Expectations
failure report and decide how to respond.

FAILURE REPORT:
{FAKE_GE_REPORT}

You may ONLY select one of these tools:
repair_duplicate_orders, repair_null_orders, repair_invalid_status,
quarantine_rows, rerun_validation, none

Respond with ONLY valid JSON, no markdown fences, no explanation outside
the JSON, matching exactly this shape:
{{
  "failure_type": "duplicate_orders" | "null_orders" | "invalid_status" | "unknown",
  "selected_tool": "repair_duplicate_orders" | "repair_null_orders" | "repair_invalid_status" | "quarantine_rows" | "rerun_validation" | "none",
  "confidence": <float 0 to 1>,
  "reasoning": "<one sentence>",
  "should_escalate": <true or false>
}}
"""

def get_live_free_models():
    """Ask OpenRouter what free models currently exist on this account."""
    resp = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()["data"]

    free_ids = []
    for m in data:
        model_id = m.get("id", "")
        pricing = m.get("pricing", {})
        prompt_cost = pricing.get("prompt", "1")
        if model_id.endswith(":free") or prompt_cost == "0":
            free_ids.append(model_id)
    return free_ids


print("Fetching live free model list from OpenRouter...")
free_models = get_live_free_models()
print(f"Found {len(free_models)} free models. Trying up to first 8.\n")

response = None
working_model = None

for model_id in free_models[:8]:
    try:
        print(f"Trying model: {model_id} ...")
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": PROMPT}],
            timeout=30,
        )
        working_model = model_id
        print(f"SUCCESS with: {model_id}\n")
        break
    except Exception as e:
        print(f"FAILED: {model_id} -> {e}\n")
        time.sleep(1)

if response is None:
    raise RuntimeError("None of the live free models worked. See errors above.")

raw_text = response.choices[0].message.content.strip()
if raw_text.startswith("```"):
    raw_text = raw_text.strip("`")
    if raw_text.startswith("json"):
        raw_text = raw_text[4:].strip()

print("RAW LLM OUTPUT:")
print(raw_text)
print()

decision = RecoveryDecision.model_validate_json(raw_text)

print("PARSED + VALIDATED DECISION:")
print(decision)
print()
print(f"working model:   {working_model}")
print(f"failure_type:    {decision.failure_type}")
print(f"selected_tool:   {decision.selected_tool}")
print(f"confidence:      {decision.confidence}")
print(f"should_escalate: {decision.should_escalate}")