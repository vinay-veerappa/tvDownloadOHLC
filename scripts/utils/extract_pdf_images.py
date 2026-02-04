
import fitz  # PyMuPDF
import os
from pathlib import Path

PDF_DIR = Path("docs/Herman")
OUTPUT_DIR = PDF_DIR / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    doc_name = pdf_path.stem.replace(" ", "_")
    
    print(f"\nProcessing: {pdf_path.name}")
    print(f"Pages: {len(doc)}")
    
    count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)
        
        if image_list:
            print(f"  Page {page_index + 1}: Found {len(image_list)} images")
        
        for image_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Filter small images (logos, icons)
            if len(image_bytes) < 2048:  # Skip < 2KB
                continue
                
            image_filename = f"{doc_name}_p{page_index + 1}_{image_index}.{image_ext}"
            image_path = OUTPUT_DIR / image_filename
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            count += 1
            
    print(f"-> Extracted {count} images from {doc_name}")

def main():
    # Find all PDFs in docs/Herman
    # Note: extracted_text is a subdir, so simple glob on PDF_DIR works
    pdfs = list(PDF_DIR.glob("*.pdf"))
    
    if not pdfs:
        print(f"No PDFs found in {PDF_DIR}")
        return

    for pdf in pdfs:
        extract_images_from_pdf(pdf)

if __name__ == "__main__":
    main()
