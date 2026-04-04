import zipfile
import re
import sys

def get_docx_text(path):
    try:
        with zipfile.ZipFile(path) as document:
            xml_content = document.read('word/document.xml').decode('utf-8')
            # Very basic XML tag removal
            text = re.sub('<[^<]+?>', '', xml_content)
            return text
    except Exception as e:
        return f"Error reading docx: {e}"

if __name__ == "__main__":
    path = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\risk profiling cleaned up.docx"
    print(get_docx_text(path))
