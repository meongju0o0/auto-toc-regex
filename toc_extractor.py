import fitz
import re
from typing import Dict, List, Pattern, Tuple, Optional


def extract_hierarchical_toc(
    pdf_path: str, 
    regex_patterns: List[Pattern],
    start_page: int = 1,
    end_page: Optional[int] = None
) -> Dict[int, List[Tuple[int, str, str, str]]]:
    structure_by_page: Dict[int, List[Tuple[int, str, str, str]]] = {}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF file: {e}")
        return {}

    if end_page is None or end_page > len(doc):
        end_page = len(doc)
    
    for page_num in range(start_page - 1, end_page):
        if page_num >= len(doc):
            break
            
        page = doc.load_page(page_num)
        text = page.get_text("text")

        all_matches_on_page = []
        for level, compiled_regex in enumerate(regex_patterns):
            for match in compiled_regex.finditer(text):
                all_matches_on_page.append((match.start(), level, match.groups()))
        
        all_matches_on_page.sort(key=lambda x: x[0])

        page_structure = []
        for _start_pos, level, groups in all_matches_on_page:
            section_num, title, page_num_str = groups

            roman_numerals = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']
            if level == 0 and title.strip().lower() in roman_numerals:
                continue

            page_structure.append((level, section_num, title, page_num_str))
        
        if page_structure:
            structure_by_page[page_num + 1] = page_structure

    doc.close()
    return structure_by_page


def format_toc_for_prompt(toc_structure: Dict[int, List[Tuple[int, str, str, str]]]) -> str:
    output_lines = []
    all_structures = []
    for page, structures in sorted(toc_structure.items()):
        all_structures.extend(structures)
    
    if not all_structures:
        return "추출된 목차 항목이 없습니다."

    for level, num, title, page_num in all_structures:
        indent = "    " * level
        page_str = page_num.strip() if page_num else "N/A"
        output_lines.append(f"{indent}> [L{level+1}: {num.strip()}] [Title: {title.strip()}] [Page: {page_str}]")
    
    return "\n".join(output_lines)


if __name__ == "__main__":
    file_name = "preface.pdf"
    
    regex_level1 = r"^(\d+)\s+([a-zA-Z].*?)(?:\s[\s\.]+\s*(\d+))?$"
    regex_level2 = r"^(\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$"
    regex_level3 = r"^(\d+\.\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$"

    hierarchical_regexes = [
        re.compile(regex_level1, re.MULTILINE),
        re.compile(regex_level2, re.MULTILINE),
        re.compile(regex_level3, re.MULTILINE)
    ]

    toc_start_page = 7
    toc_end_page = 17

    toc_structure = extract_hierarchical_toc(
        file_name, 
        hierarchical_regexes, 
        start_page=toc_start_page, 
        end_page=toc_end_page
    )

    print("--- Hierarchical TOC Extraction Results ---")
    for page, structures in sorted(toc_structure.items()):
        for level, num, title, page_num in structures:
            indent = "    " * level
            page_str = page_num.strip() if page_num else "N/A"
            print(f"{indent}> [L{level+1}: {num.strip()}] [Title: {title.strip()}] [Page: {page_str}]")
