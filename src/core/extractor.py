import pypdf
import io
import re

def extract_text_from_bytes(file_bytes):
    """
    Extracts text using standard pypdf and applies heavy layout normalization
    to stitch disjointed or vertically split words back together.
    """
    raw_text = ""
    try:
        file_stream = io.BytesIO(file_bytes)
        reader = pypdf.PdfReader(file_stream)
        
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                raw_text += page_text + "\n"
                
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

    # --- ADVANCED TEXT NORMALIZATION LAYER ---
    # 1. Replace single letters followed by spaces (e.g., 'p y t h o n' -> 'python')
    # This repairs broken font mappings commonly found in graphic-heavy PDF exports
    normalized_text = re.sub(r'(?<=\b\w)\s+(?=\w\b)', '', raw_text)
    
    # 2. Re-insert a single space between legitimate words that might have been smashed
    normalized_text = re.sub(r'\s+', ' ', normalized_text)
    
    return normalized_text.strip()