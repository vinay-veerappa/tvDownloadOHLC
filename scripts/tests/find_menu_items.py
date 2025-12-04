from bs4 import BeautifulSoup

def find_menu_items():
    with open("replay_debug.txt", "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for any element with text "Select bar"
    elements = soup.find_all(string=lambda text: text and "Select bar" in text)
    print(f"Found {len(elements)} elements with 'Select bar'.")
    
    for el in elements:
        parent = el.parent
        print(f"Text: {el.strip()}")
        print(f"Tag: {parent.name}")
        print(f"Attrs: {parent.attrs}")
        
        # Check siblings
        print("Siblings:")
        for sib in parent.next_siblings:
            if sib.name:
                print(f"  Tag: {sib.name}")
                print(f"  Attrs: {sib.attrs}")
        
        # Check parent's siblings (if the text is deep inside)
        grandparent = parent.parent
        if grandparent:
            print("Parent's Siblings:")
            for sib in grandparent.next_siblings:
                if sib.name:
                    print(f"  Tag: {sib.name}")
                    print(f"  Attrs: {sib.attrs}")
                    
        print("-" * 20)

if __name__ == "__main__":
    find_menu_items()
