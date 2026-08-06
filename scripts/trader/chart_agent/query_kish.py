"""Query KB for Kish/TCM analysis method and levels."""
import json, urllib.request, sys

def ask_kb(question, k=8):
    body = json.dumps({"question": question, "k": k}).encode()
    req = urllib.request.Request("http://127.0.0.1:8900/ask", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("answer", ""), data.get("sources", [])

questions = [
    ("KISH/TCM METHOD",
     "How does Kish and TCM analyze charts for bias? What are the 7 Rules? What levels does Kish use for analysis - midnight open, dealing range mids, session mids, Asia mid, London mid, PDH, PDL? How does Kish determine the dealing range and premium/discount?"),
    ("KISH LEVELS",
     "What specific levels does Kish/TCM use? PDM (prior day mid), dealing range equilibrium, session midpoints, Asia mid, London mid, NY mid. What are the 7 Rules and what levels do they reference?"),
    ("KISH SESSION ANALYSIS",
     "How does Kish analyze each session (Asia, London, NY) for trade setups? What does he look for at each session open? How does he use the midnight open and session mids?"),
    ("KISH DEALING RANGE",
     "How does Kish define the dealing range? Is it PDH-PDL or something else? How does he calculate premium and discount? What is the PDM (prior day mid) and how is it used?"),
]

for title, q in questions:
    answer, sources = ask_kb(q, 10)
    sys.stdout.buffer.write(f"\n=== {title} ===\n".encode())
    sys.stdout.buffer.write(answer[:2000].encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(f"\n  ({len(sources)} sources)\n".encode())
    sys.stdout.buffer.flush()