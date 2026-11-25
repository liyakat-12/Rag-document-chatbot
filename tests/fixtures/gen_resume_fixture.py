"""Generate a fictional one-page resume PDF for answer-quality manual tests.

Invented identity only — no real contact details.
"""

from __future__ import annotations

import json
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent
PDF_NAME = "fictional_resume_jordan_blake.pdf"
QUESTIONS_NAME = "fictional_resume_questions.jsonl"


def build_pdf(path: Path) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False, margin=12)
    pdf.add_page()
    pdf.set_margins(14, 12, 14)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(w=180, h=8, text="Jordan Blake")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        w=180,
        h=5,
        text="Cityville, ST 00000 · jordan.blake.example@mail.test · LinkedIn | Github",
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        w=180,
        h=5,
        text=(
            "Software engineer with hands-on experience in retrieval systems and "
            "data pipelines. Built an internal search prototype with R2 = 0.69 "
            "relevance correlation and a CGPA: 7.92 / 10 academic record."
        ),
    )
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "Internships", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        w=180,
        h=5,
        text=(
            "Intern, Northwind Analytics (Jun 2023 - Aug 2023). Reduced batch "
            "ETL runtime by 35% and documented a scheme expense ratio of 0.20% "
            "for an internal fund dashboard demo."
        ),
    )
    pdf.multi_cell(
        w=180,
        h=5,
        text=(
            "Intern, Contoso Labs (Jan 2024 - May 2024). Shipped a B.Tech project "
            "bridge that tagged 1,200 support tickets with 92% precision."
        ),
    )
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "Projects", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    projects = [
        "DocuSearch Lite: offline RAG demo indexing 50 PDFs with hybrid FAISS+BM25.",
        "Latency Board: tracked p95 chat latency under 800 ms across 10k queries.",
        "Fund Code Parser: extracted codes like HDFC/O/E/MIF/07/04/0015 from SIDs.",
        "Campus Portal: cut average page load from 2.4 s to 1.1 s for 4,500 users.",
    ]
    for p in projects:
        pdf.multi_cell(w=180, h=5, text=f"- {p}")
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "Education", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        w=180,
        h=5,
        text=(
            "B.Tech in Computer Science, Riverview Institute of Technology "
            "(2020-2024). Thesis on sentence selection for extractive QA; "
            "reported R2 = 0.69 on a held-out set. Note: campus placement "
            "offer letter also mentions a 35% scholarship (different context "
            "from the ETL 35% runtime reduction above)."
        ),
    )
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "Skills", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        w=180,
        h=5,
        text="Python, FastAPI, FAISS, BM25, Streamlit, SQLite, pytest, Docker.",
    )
    pdf.output(str(path))


def build_questions(path: Path) -> None:
    rows = [
        {
            "id": "fr_q1_name",
            "query": "What is the candidate's name on the resume?",
            "expected": "Jordan Blake",
            "answerable": True,
            "key_facts": ["Jordan Blake"],
        },
        {
            "id": "fr_q2_cgpa",
            "query": "What CGPA is listed?",
            "expected": "7.92 / 10",
            "answerable": True,
            "key_facts": ["7.92"],
        },
        {
            "id": "fr_q3_degree",
            "query": "What degree did Jordan complete?",
            "expected": "B.Tech in Computer Science",
            "answerable": True,
            "key_facts": ["B.Tech", "Computer Science"],
        },
        {
            "id": "fr_q4_r2",
            "query": "What R2 relevance correlation is reported?",
            "expected": "0.69",
            "answerable": True,
            "key_facts": ["0.69"],
        },
        {
            "id": "fr_q5_etl",
            "query": "By how much did the Northwind Analytics internship reduce ETL runtime?",
            "expected": "35%",
            "answerable": True,
            "key_facts": ["35%"],
            "notes": "35% also appears as scholarship — number appears twice",
        },
        {
            "id": "fr_q6_expense",
            "query": "What expense ratio appears in the internship description?",
            "expected": "0.20%",
            "answerable": True,
            "key_facts": ["0.20%"],
        },
        {
            "id": "fr_q7_fund_code",
            "query": "Which fund scheme code example is mentioned in projects?",
            "expected": "HDFC/O/E/MIF/07/04/0015",
            "answerable": True,
            "key_facts": ["HDFC/O/E/MIF/07/04/0015"],
        },
        {
            "id": "fr_q8_skills",
            "query": "Which search libraries are listed under skills?",
            "expected": "FAISS, BM25",
            "answerable": True,
            "key_facts": ["FAISS", "BM25"],
        },
        {
            "id": "fr_q9_near_miss_salary",
            "query": "What was Jordan Blake's annual salary at Contoso Labs?",
            "expected": "not in document",
            "answerable": False,
            "key_facts": [],
            "notes": "near-miss unanswerable — internship exists, salary does not",
        },
        {
            "id": "fr_q10_near_miss_phd",
            "query": "Where did Jordan complete a Ph.D. in machine learning?",
            "expected": "not in document",
            "answerable": False,
            "key_facts": [],
            "notes": "near-miss unanswerable — B.Tech only",
        },
    ]
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    pdf_path = OUT / PDF_NAME
    q_path = OUT / QUESTIONS_NAME
    build_pdf(pdf_path)
    build_questions(q_path)
    print("wrote", pdf_path)
    print("wrote", q_path)


if __name__ == "__main__":
    main()
