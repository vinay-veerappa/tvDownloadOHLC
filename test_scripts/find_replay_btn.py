from bs4 import BeautifulSoup

def find_replay_button():
    with open("page_source_debug.txt", "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for buttons with 'replay' in attributes or text
    buttons = soup.find_all('button')
    print(f"Found {len(buttons)} buttons.")
    
    for btn in buttons:
        attrs = str(btn.attrs)
        text = btn.get_text()
        if 'replay' in attrs.lower() or 'replay' in text.lower():
            print(f"POTENTIAL MATCH: {btn}")
            print(f"  Attrs: {btn.attrs}")
            print(f"  Text: {text}")
            print("-" * 20)

    # Also look for divs that might be the button
    divs = soup.find_all('div')
    for div in divs:
        attrs = str(div.attrs)
        if 'replay' in attrs.lower():
             print(f"POTENTIAL DIV MATCH: {div.attrs}")

if __name__ == "__main__":
    find_replay_button()
