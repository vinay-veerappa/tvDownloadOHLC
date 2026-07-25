"""
ollama_bridge.py
================
Unified Ollama LLM Bridge for tvDownloadOHLC.
Provides an interface to call any model installed locally or cloud-routed in Ollama
(e.g., qwen3.6, deepseek-v4-pro:cloud, codegemma:7b-instruct, kimi-k2.7-code:cloud, gemma4:31b-cloud).

Usage:
  python -m scripts.utils.ollama_bridge --list
  python -m scripts.utils.ollama_bridge --model qwen3.6 --prompt "Summarize this strategy..."
  python -m scripts.utils.ollama_bridge --model deepseek-v4-pro:cloud --prompt "Audit this code..."
"""
import os
import sys
import json
import urllib.request
import urllib.error
import argparse
from typing import Dict, Any, List, Optional

raw_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
if not raw_host.startswith("http"):
    raw_host = f"http://{raw_host}"
raw_host = raw_host.replace("0.0.0.0", "127.0.0.1")
if raw_host.count(":") == 1: # e.g. http://127.0.0.1 without port
    raw_host = f"{raw_host}:11434"
OLLAMA_HOST = raw_host


def list_ollama_models() -> List[Dict[str, Any]]:
    """Fetches list of all available models from Ollama server."""
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("models", [])
    except Exception as e:
        print(f"[ollama_bridge] Error connecting to Ollama at {OLLAMA_HOST}: {e}")
    return []


def query_ollama(
    prompt: str,
    model: str = "qwen3.6:latest",
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    stream: bool = False
) -> Optional[str]:
    """Sends a completion request to the specified Ollama model."""
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "stream": stream
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=json_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            if response.status == 200:
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json.get("response", "")
    except urllib.error.URLError as e:
        print(f"[ollama_bridge] HTTP Error during request to model '{model}': {e}")
    except Exception as e:
        print(f"[ollama_bridge] Error querying model '{model}': {e}")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ollama Local & Cloud LLM Bridge Utility.")
    parser.add_argument("--list", action="store_true", help="List all installed Ollama models.")
    parser.add_argument("--model", type=str, default="qwen3.6:latest", help="Model name to query.")
    parser.add_argument("--prompt", type=str, default=None, help="Prompt text to send.")
    parser.add_argument("--system", type=str, default=None, help="Optional system prompt.")
    parser.add_argument("--output", type=str, default=None, help="Save response directly to output filepath to save tokens.")
    
    args = parser.parse_args()

    if args.list:
        models = list_ollama_models()
        print(f"--- AVAILABLE OLLAMA MODELS ({len(models)}) ---")
        for m in models:
            name = m.get("name", "unknown")
            size_mb = round(m.get("size", 0) / (1024 * 1024), 1)
            print(f" - {name:35s} (Size: {size_mb} MB)")
    elif args.prompt:
        print(f"Querying Ollama model [{args.model}]...")
        ans = query_ollama(args.prompt, model=args.model, system_prompt=args.system)
        if ans:
            sys.stdout.reconfigure(encoding='utf-8')
            if args.output:
                os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(ans)
                print(f"[ollama_bridge] Saved {len(ans)} chars to file: {args.output}")
            else:
                print("\n--- RESPONSE ---")
                print(ans)
        else:
            print("Failed to get response from model.")
    else:
        parser.print_help()
