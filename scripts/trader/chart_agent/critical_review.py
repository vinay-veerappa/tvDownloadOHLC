"""Critical review of the chart agent plan using multiple LLMs."""
import requests
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent.parent
plan = (_REPO / "docs" / "architecture" / "CHART_AGENT_FEATURE_AUDIT.md").read_text(encoding="utf-8")
tbp = Path("C:/Users/vinay/Downloads/Trader_Blue_Print_Series.md").read_text(encoding="utf-8")

prompt = f"""You are a critical reviewer for a trading AI system plan. Review the following plan and the TBP reference.

Find problems, contradictions, and missing pieces. Be specific and harsh.

Key questions:
1. Are the 7 Rules entry rules or bias rules? Should they be in a daily bias prompt?
2. Is the submission range (2PM-6:15PM ET OHLC) correctly integrated?
3. Are the session time definitions correct for ICT futures trading?
4. Will feeding hundreds of FVG/OB rows to an LLM cause context degradation?
5. Is the vision verification loop sound or will it have anchoring bias?
6. What is missing that an ICT trader would immediately notice?
7. Is the dealing range definition wrong (PDH-PDL vs structural swing)?
8. Should derived data be fixed before or after the reasoner rewrite?
9. Is midnight open meaningful for futures or is it a forex concept?
10. Are there DST timezone risks?

PLAN:
{plan}

TBP REFERENCE:
{tbp}"""

models = [
    ("deepseek-v4-pro:cloud", "data/vision/critical_review_deepseek.txt"),
    ("gemma4:31b-cloud", "data/vision/critical_review_gemma4.txt"),
]

for model, outfile in models:
    print(f"Reviewing with {model}...", flush=True)
    try:
        resp = requests.post("http://localhost:11434/api/generate", json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 262144, "num_predict": 8192}
        }, timeout=300)
        result = resp.json().get("response", "ERROR")
        Path(outfile).write_text(result, encoding="utf-8")
        print(f"  Saved to {outfile} ({len(result)} chars)")
    except Exception as e:
        print(f"  ERROR: {e}")