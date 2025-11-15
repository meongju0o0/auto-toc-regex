import os
import re
import traceback
from xmlrpc import client
from dotenv import load_dotenv
from typing import List
from openai import OpenAI

from toc_extractor import extract_hierarchical_toc, format_toc_for_prompt
from pdf_parser import extract_text_for_prompt

JUDGE_PROMPT_TEMPLATE = \
r"""
당신은 PDF 목차 추출(TOC) Regex의 성능을 평가하는 '심판' LLM입니다.

[평가 기준]
1.  ✅ Correct: 정답(Ground Truth)과 정확히 일치하며, 불필요한 텍스트가 없음.
2.  ⚠️ Suboptimal: 정답(Ground Truth)을 모두 포함하지만, 불필요한 텍스트도 일부 포함됨.
3.  ❌ Hallucinatory: Regex가 작동하지 않거나, 정답을 하나도 추출하지 못하거나, 정답이 아닌 텍스트만 추출함.
4.  🚫 Missing: LLM이 Regex 생성을 포기함.

[사고 과정 (Chain-of-Thought)]
당신은 [실제 평가 작업]을 수행할 때, 반드시 다음 5단계를 거쳐 생각해야 합니다.

1.  **[오류 확인]** `Regex 실행 결과 (Extracted Data)`에 `Traceback`이나 `Error`가 포함되어 있습니까?
    -   만약 그렇다면, 즉시 `Hallucinatory`로 분류하고 3단계로 넘어갑니다.
2.  **[분류 결정]** 위의 1~2단계 분석을 바탕으로 4가지 평가 기준 중 하나를 결정합니다.
    -   (예: 1단계에서 오류 발생 -> Hallucinatory)
    -   (예: 2단계에서 누락은 없으나 불필요한 항목 발견 -> Suboptimal)
    -   (예: 2단계에서 누락도 없고 불필요한 항목도 없음 -> Correct)
    -   (예: 2단계에서 누락된 항목이 1개라도 있음 -> Hallucinatory)
3.  **[이유 작성]** 3단계에서 왜 그렇게 분류했는지 구체적인 이유를 서술합니다.
4.  **[JSON 출력]** 최종 결과를 [출력 포맷]에 맞춰 JSON으로 생성합니다.

---

[평가 예시 (Golden Set)]
다음은 당신이 따라야 할 실제 평가 예시입니다.

### 예시 1
- **Regex Level 1:** ```^(\d+)\s+([a-zA-Z].*?)(?:\s[\s\.]+\s*(\d+))?$```
- **Regex Level 2:** ```^(\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$```
- **Regex Level 3:** ```^(\d+\.\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$```

- **Extracted Data:** 
> [L1: 1] [Title: Data Mining] [Page: N/A]
    > [L2: 1.1] [Title: What is Data Mining?] [Page: 1]
        > [L3: 1.1.1] [Title: Statistical Modeling] [Page: 1]
        > [L3: 1.1.2] [Title: Machine Learning] [Page: 2]
        > [L3: 1.1.3] [Title: Computational Approaches to Modeling] [Page: 2]
        > [L3: 1.1.4] [Title: Summarization] [Page: 3]
        > [L3: 1.1.5] [Title: Feature Extraction] [Page: 4]
    > [L2: 1.2] [Title: Statistical Limits on Data Mining] [Page: 4]
        > [L3: 1.2.1] [Title: Total Information Awareness] [Page: 5]
        > [L3: 1.2.2] [Title: Bonferroni's Principle] [Page: 5]
        > [L3: 1.2.3] [Title: An Example of Bonferroni's Principle] [Page: 6]
        > [L3: 1.2.4] [Title: Exercises for Section 1.2] [Page: 7]
    > [L2: 1.3] [Title: Things Useful to Know] [Page: 7]
        > [L3: 1.3.1] [Title: Importance of Words in Documents] [Page: 8]
        > [L3: 1.3.2] [Title: Hash Functions] [Page: 9]
        > [L3: 1.3.3] [Title: Indexes] [Page: 10]
        > [L3: 1.3.4] [Title: Secondary Storage] [Page: 11]
        > [L3: 1.3.5] [Title: The Base of Natural Logarithms] [Page: 12]
        > [L3: 1.3.6] [Title: Power Laws] [Page: 13]
        > [L3: 1.3.7] [Title: Exercises for Section 1.3] [Page: 15]
    > [L2: 1.4] [Title: Outline of the Book] [Page: 15]
> [L1: 2] [Title: MapReduce and the New Software Stack] [Page: N/A]
    > [L2: 2.1] [Title: Distributed File Systems] [Page: 22]
        > [L3: 2.1.1] [Title: Physical Organization of Compute Nodes] [Page: 22]
        > [L3: 2.1.2] [Title: Large-Scale File-System Organization] [Page: 23]
    > [L2: 2.2] [Title: MapReduce] [Page: 24]
        > [L3: 2.2.1] [Title: The Map Tasks] [Page: 25]
        > [L3: 2.2.2] [Title: Grouping by Key] [Page: 26]
        > [L3: 2.2.3] [Title: The Reduce Tasks] [Page: 27]
        > [L3: 2.2.4] [Title: Combiners] [Page: 27]
        > [L3: 2.2.5] [Title: Details of MapReduce Execution] [Page: 28]
        > [L3: 2.2.6] [Title: Coping With Node Failures] [Page: 29]
        > [L3: 2.2.7] [Title: Exercises for Section 2.2] [Page: 30]
- **[평가 결과]**
    - **분류:** Optimal
    - **이유:** 모든 정답 항목이 정확히 추출되었고, 불필요한 텍스트가 포함되지 않았습니다.

### 예시 2
- **Regex Level 1:** ```^(Chapter\s+\d+\n[A-Z].*)$```
- **Regex Level 2:** ```^(\d+\.\d+\s+[A-Z].*)$```
- **Regex Level 3:** ```^(\d+\.\d+\.\d+\s+[A-Z].*)$```

- **Extracted Data:** 
Traceback (most recent call last):
  File "/home/meongju0o0/auto_regex/toc_auto_regex.py", line 68, in <module>
    toc_structure = extract_hierarchical_toc(
                    ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/meongju0o0/auto_regex/toc_auto_regex.py", line 38, in extract_hierarchical_toc
    section_num, title, page_num_str = groups
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: not enough values to unpack (expected 3, got 1)

- **[평가 결과]**
    - **분류:** Hallucinatory
    - **이유:** Regex가 작동하여 무언가를 추출했으나, Ground Truth와 일치하는 항목이 하나도 없고 목차가 아닌 본문의 리스트를 추출했습니다.
---

[실제 평가 작업]
이제 위의 평가 기준과 예시를 바탕으로, 아래의 새로운 작업에 대해 평가를 수행하십시오.

## 1. 평가 대상 PDF 텍스트 (목차 페이지만):
{pdf_raw_text}

## 1. LLM이 생성한 Regex:
{regex_strings_str}

## 2. Regex 실행 결과 (Extracted Data):
{extracted_data_str}

---

[출력 포맷]
당신의 최종 답변은 반드시 다음 구조를 따르는 JSON 객체 **하나**여야 합니다.
(설명이나 추가 텍스트 없이 JSON만 출력하십시오.)
예시:
{{
    "classification": "Correct" | "Suboptimal" | "Hallucinatory" | "Missing",
    "reason": "당신이 그렇게 분류한 구체적인 이유를 여기에 작성하십시오."
}}
"""


def evaluate_toc_regex(
    pdf_path: str,
    regex_strings: List[str],
    start_page: int,
    end_page: int,
    judge_model: str = "gpt-5-nano"
):
    pdf_raw_text = extract_text_for_prompt(pdf_path, start_page, end_page)
    
    extracted_data_str = ""
    try:
        hierarchical_regexes = [re.compile(r, re.MULTILINE) for r in regex_strings]
        toc_structure = extract_hierarchical_toc(
            pdf_path,
            hierarchical_regexes,
            start_page=start_page,
            end_page=end_page
        )
        extracted_data_str = format_toc_for_prompt(toc_structure)
    except Exception as e:
        print(f"Regex 실행 중 오류 발생: {e}")
        extracted_data_str = traceback.format_exc()

    final_prompt = JUDGE_PROMPT_TEMPLATE.format(
        pdf_raw_text=pdf_raw_text,
        regex_strings_str="\n".join(regex_strings),
        extracted_data_str=extracted_data_str
    )
    
    print("--- '심판 LLM'에게 평가를 요청합니다... ---")
    try:
        response = client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "user", "content": final_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"'심판 LLM' 호출 중 오류 발생: {e}"


if __name__ == "__main__":
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    file_name = "preface.pdf"
    toc_start_page = 7
    toc_end_page = 17

    # # (성공 케이스 예시 - 예시 1의 Correct 유발)
    # llm_generated_regex_strings = [
    #     r"^(\d+)\s+([a-zA-Z].*?)(?:\s[\s\.]+\s*(\d+))?$",
    #     r"^(\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$",
    #     r"^(\d+\.\d+\.\d+)\s+(.+?)(?:\s[\s\.]+\s*(\d+))?$"
    # ]

    # (실패 케이스 예시 - 예시 2의 ValueError 유발)
    llm_generated_regex_strings = [
        r"^(Chapter\s+\d+\n[A-Z].*)$",
        r"^(\d+\.\d+\s+[A-Z].*)$",
        r"^(\d+\.\d+\.\d+\s+[A-Z].*)$"
    ]
    
    evaluation_result = evaluate_toc_regex(
        pdf_path=file_name,
        regex_strings=llm_generated_regex_strings,
        start_page=toc_start_page,
        end_page=toc_end_page,
        judge_model="gpt-4o"
    )
    
    print("\n--- '심판 LLM'의 최종 평가 결과 ---")
    print(evaluation_result)