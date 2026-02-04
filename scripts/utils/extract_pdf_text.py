
import os
import sys
from pathlib import Path

try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        print("Error: neither pypdf nor PyPDF2 is installed.")
        sys.exit(1)

def extract_text(pdf_path, output_path):
    print(f"Extracting {pdf_path.name}...")
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        text = []
        for i, page in enumerate(reader.pages):
            text.append(f"--- Page {i+1} ---")
            text.append(page.extract_text())
        
        full_text = "\n".join(text)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
            
        print(f"Saved to {output_path}")
        return True
    except Exception as e:
        print(f"Failed to extract {pdf_path.name}: {e}")
        return False

def main():
    target_dir = Path(r"c:\Users\vinay\tvDownloadOHLC\docs\herman")
    output_dir = target_dir / "extracted_text"
    output_dir.mkdir(exist_ok=True)
    
    files = list(target_dir.glob("*.pdf"))
    if not files:
        print("No PDF files found.")
        return

    for pdf_file in files:
        output_file = output_dir / (pdf_file.stem + ".txt")
        extract_text(pdf_file, output_file)

if __name__ == "__main__":
    main()
