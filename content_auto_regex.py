import fitz
import re
from typing import Dict, List, Pattern, Tuple, Optional


def extract_hierarchical_structure(
    pdf_path: str,
    regex_patterns: List[Pattern],
    start_page: int = 1,
    end_page: Optional[int] = None
) -> List[Tuple[int, str]]:
    structures: List[Tuple[int, str]] = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF file: {e}")
        return []

    for page_num in range(start_page - 1, end_page):
        if page_num >= len(doc):
            break

        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        page_structure = []
        
        for level, compiled_regex in enumerate(regex_patterns):
            matches = compiled_regex.findall(text)
            for match_string in matches:
                page_structure.append((level, match_string.strip()))
        
        if page_structure:
            structures.extend(page_structure)

    doc.close()
    return structures


if __name__ == "__main__":
    file_name = "book.pdf"
    
    regex_level1 = re.compile(r"^(Chapter\s+\d+\n[A-Z].*)$", re.MULTILINE)
    regex_level2 = re.compile(r"^(\d+\.\d+\s+[A-Z].*)$", re.MULTILINE)
    regex_level3 = re.compile(r"^(\d+\.\d+\.\d+\s+[A-Z].*)$", re.MULTILINE)
    
    hierarchical_regexes = [regex_level1, regex_level2, regex_level3]

    extracted_structure = extract_hierarchical_structure(file_name, hierarchical_regexes, 19, 502)

    print("--- Hierarchical Contents Architecture ---")
    for level, full_string in extracted_structure:
        indent = "    " * level
        cleaned_string = full_string.replace('\n', ' - ')
        print(f"{indent}> [L{level+1}] {cleaned_string}")