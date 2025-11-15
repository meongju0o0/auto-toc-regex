import fitz
from typing import Optional

def extract_text_for_prompt(pdf_path: str, start_page: int, end_page: Optional[int] = None) -> str:
    all_text = ""
    try:
        doc = fitz.open(pdf_path)
        if end_page is None or end_page > len(doc):
            end_page = len(doc)
        
        for page_num in range(start_page - 1, end_page):
            if page_num >= len(doc):
                break
            page = doc.load_page(page_num)
            all_text += f"--- Page {page_num + 1} ---\n{page.get_text('text')}\n\n"
        doc.close()
    except Exception as e:
        return f"PDF 텍스트 추출 중 오류 발생: {e}"
    return all_text