"""
tools/resume_parser.py
Simple .docx resume reader used by main.py
"""
import docx
import os
from config import APP_CONFIG

def get_resume_text(file_path: str) -> str:
    """
    Extracts all text from a .docx file.

    Returns:
        String with document text or an error message starting with 'Error:'.
    """
    if not os.path.exists(file_path):
        return f"Error: Resume file not found at {file_path}"
    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return '\n'.join(paragraphs)
    except Exception as e:
        return f"Error parsing resume file: {e}"

if __name__ == '__main__':
    print("--- Testing Resume Parser ---")
    p = APP_CONFIG.BASE_RESUME_PATH
    txt = get_resume_text(p)
    if txt.startswith("Error:"):
        print(txt)
    else:
        print(f"Successfully parsed resume from: {p}\n")
        print("--- Resume Content (first 500 chars) ---")
        print(txt[:500] + "...")
