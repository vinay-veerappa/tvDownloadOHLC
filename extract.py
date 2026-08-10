import json
with open(r'C:\Users\vinay\.gemini\antigravity\brain\116e21e3-b8b6-465b-b67a-4acb30b7e94e\.system_generated\logs\transcript_full.jsonl', 'r') as f:
    for line in f:
        if 'send_message' in line and 'Research Report' in line:
            msg = json.loads(line)['tool_calls'][0]['args']['Message']
            with open(r'C:\Users\vinay\.gemini\antigravity\brain\ffdfb8e8-c1d0-416c-ab8c-33c2029b7adc\scratch\patch_code.md', 'w', encoding='utf-8') as out:
                out.write(msg)
