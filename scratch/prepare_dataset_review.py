"""Prepare Dataset & Architecture Review Prompt

Prepares review prompt for master_rule_catalog.json and wargaming_fine_tuning_dataset.jsonl.
"""
from pathlib import Path
import json

REPO = Path(__file__).parent.parent
catalog_file = REPO / "docs" / "profiler" / "master_rule_catalog.json"
dataset_file = REPO / "data" / "wargaming_fine_tuning_dataset.jsonl"

sample_records = []
if dataset_file.exists():
    with open(dataset_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 3:
                break
            sample_records.append(json.loads(line))

prompt_file = REPO / "scratch" / "dataset_review_prompt.txt"
prompt_file.write_text(f"""You are an AI fine-tuning architect and quantitative trading system auditor.

Review our Master Rule Catalog (`docs/profiler/master_rule_catalog.json`) and sample records from our newly generated Fine-Tuning Dataset (`data/wargaming_fine_tuning_dataset.jsonl`).

Provide a thorough audit addressing:
1. **Instruction-Tuning Format & Prompt Quality**: Is the prompt/completion structure optimal for fine-tuning LLMs (e.g., Llama-3, Qwen-2.5, DeepSeek R1, Mistral) to behave as an expert daily market profiler and wargamer?
2. **Rule Completeness & Logic Alignment**: Are Matt Mickey & Austin's core rules (R1 4-hour open print touch, DNP 5-hour trend, DWP afternoon range, R2 thigh gap, P12 06:00-07:00 early rejection, NY Opening Handshake) accurately represented?
3. **Data Quality & Leakage Prevention**: Confirm that the prompt contains ZERO future RTH data, keeping the pre-market wargaming 08:30 AM cutoff 100% strict.
4. **Actionable Recommendations**: How can we expand or enrich this dataset to train local Ollama models (or fine-tune via Unsloth/LoRA)?

--- MASTER RULE CATALOG ---
{catalog_file.read_text(encoding='utf-8') if catalog_file.exists() else 'N/A'}

--- SAMPLE FINE-TUNING DATASET RECORDS (3 Pairs) ---
{json.dumps(sample_records, indent=2)}
""", encoding="utf-8")

print(f"Wrote dataset review prompt to {prompt_file}")
