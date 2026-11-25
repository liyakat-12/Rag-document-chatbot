"""Build evals/data/questions.jsonl drafts from extracted corpus text.

All items are label_source=draft. Spans are copied from evals/corpus/_extracted_pages.json.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from evals.schema import GoldItem, Question, write_questions

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "corpus" / "_extracted_pages.json"
OUT = Path(__file__).resolve().parent / "questions.jsonl"


def span(pages: dict, filename: str, page: int, needle: str) -> GoldItem:
    """Find needle in page text (case-sensitive preferred) and return exact substring."""
    text = pages[filename][page - 1]["text"]
    idx = text.find(needle)
    if idx < 0:
        # try collapsed whitespace search
        flat = " ".join(text.split())
        nflat = " ".join(needle.split())
        idx2 = flat.find(nflat)
        if idx2 < 0:
            raise ValueError(f"span not found in {filename} p{page}: {needle!r}")
        # fall back to needle as stored (still from source intent)
        return GoldItem(filename=filename, page=page, span=needle)
    return GoldItem(filename=filename, page=page, span=text[idx : idx + len(needle)])


def main() -> None:
    pages = json.loads(EXTRACTED.read_text(encoding="utf-8"))
    qs: list[Question] = []

    def add(
        qid: str,
        query: str,
        category: str,
        answerable: bool,
        gold: list[GoldItem],
        key_facts: list[str],
        notes: str = "",
    ) -> None:
        qs.append(
            Question(
                id=qid,
                query=query,
                category=category,
                answerable=answerable,
                gold=gold,
                key_facts=key_facts,
                split="test",  # assigned later
                label_source="draft",
                notes=notes,
            )
        )

    # ---- smoke / fixtures ----
    add(
        "factual_ada_name",
        "Who is the candidate named in the DocuMind smoke test resume?",
        "factual",
        True,
        [span(pages, "smoke_ada2.pdf", 1, "Candidate: Ada Lovelace")],
        ["Ada Lovelace"],
    )
    add(
        "paraphrase_ada_skill",
        "What technical skill is listed for Ada in the smoke resume?",
        "paraphrase",
        True,
        [span(pages, "smoke_ada2.pdf", 1, "Skill: Analytical Engine")],
        ["Analytical Engine"],
    )
    add(
        "factual_grace_name",
        "What is the name on the performance resume?",
        "factual",
        True,
        [span(pages, "_smoke_perf.pdf", 1, "Name: Grace Hopper")],
        ["Grace Hopper"],
    )
    add(
        "exact_grace_skill",
        "Which compiler skill is attributed to Grace Hopper?",
        "exact_identifier",
        True,
        [span(pages, "_smoke_perf.pdf", 1, "Skill: COBOL Compiler")],
        ["COBOL Compiler"],
    )
    add(
        "factual_rrf",
        "What does Reciprocal Rank Fusion combine according to the QA design doc?",
        "factual",
        True,
        [span(pages, "qa_design.pdf", 1, "Reciprocal Rank Fusion combines FAISS and BM25.")],
        ["FAISS", "BM25"],
    )

    # ---- policy / invoice / api codes ----
    add(
        "number_annual_leave",
        "How many annual paid leave days do full-time employees get?",
        "number_or_date",
        True,
        [span(pages, "policy_leave_entitlement.pdf", 1, "Annual paid leave entitlement for full-time employees is 18 days.")],
        ["18"],
    )
    add(
        "number_sick_leave",
        "What is the sick leave entitlement per calendar year?",
        "number_or_date",
        True,
        [span(pages, "policy_leave_entitlement.pdf", 1, "Sick leave entitlement is 12 days per calendar year.")],
        ["12"],
    )
    add(
        "exact_policy_id",
        "What is the Policy ID for the Acme leave handbook?",
        "exact_identifier",
        True,
        [span(pages, "policy_leave_entitlement.pdf", 1, "Policy ID: ACME-HR-LEAVE-2024.")],
        ["ACME-HR-LEAVE-2024"],
    )
    add(
        "table_emp_remaining_annual",
        "For employee EMP-4412, how many annual leave days remain?",
        "table",
        True,
        [span(pages, "policy_leave_entitlement.pdf", 1, "Annual | 18 | 5 | 13")],
        ["13", "EMP-4412"],
        notes="Table row; remaining column is 13",
    )
    add(
        "exact_mgr_code",
        "What manager approval code is required for unpaid leave?",
        "exact_identifier",
        True,
        [span(pages, "policy_leave_entitlement.pdf", 1, "manager approval code MGR-OK-77.")],
        ["MGR-OK-77"],
    )
    add(
        "number_invoice_total",
        "What is the total due on invoice INV-2023-Q3-0091?",
        "number_or_date",
        True,
        [span(pages, "invoice_fixture_q3.pdf", 1, "Total due: 1501.20.")],
        ["1501.20"],
    )
    add(
        "table_sku_b220_amount",
        "What is the line amount for SKU-B220?",
        "table",
        True,
        [span(pages, "invoice_fixture_q3.pdf", 1, "SKU-B220 Sensor kit Qty 10 Unit 89.00 Amount 890.00")],
        ["890.00", "SKU-B220"],
    )
    add(
        "exact_po_number",
        "What purchase order number is listed on the invoice fixture?",
        "exact_identifier",
        True,
        [span(pages, "invoice_fixture_q3.pdf", 1, "Purchase order: PO-77821.")],
        ["PO-77821"],
    )
    add(
        "exact_dmapi_4290",
        "What does error code DMAPI-4290 mean?",
        "exact_identifier",
        True,
        [span(pages, "api_error_codes.pdf", 1, "DMAPI-4290 RateLimited: client exceeded 60 requests per minute.")],
        ["RateLimited", "60"],
    )
    add(
        "number_dmapi_retry",
        "How long should a client wait before retrying after DMAPI-4290?",
        "number_or_date",
        True,
        [span(pages, "api_error_codes.pdf", 1, "for DMAPI-4290 wait 30 seconds then retry with jitter.")],
        ["30 seconds"],
    )
    add(
        "factual_dmapi_5007",
        "What does DMAPI-5007 indicate?",
        "factual",
        True,
        [span(pages, "api_error_codes.pdf", 1, "DMAPI-5007 UpstreamTimeout: embedding provider timed out after 8s.")],
        ["UpstreamTimeout", "8s"],
    )

    # ---- resumes ----
    add(
        "factual_liyakat_location",
        "Where is Liyakat Hussain based according to the resume?",
        "factual",
        True,
        [span(pages, "Liyakat_DataScientist_Resume.pdf", 1, "Srinagar, India")],
        ["Srinagar"],
    )
    add(
        "exact_liyakat_phone",
        "What phone number is listed for Liyakat Hussain?",
        "exact_identifier",
        True,
        [span(pages, "Liyakat_DataScientist_Resume.pdf", 1, "+91 7889448874")],
        ["7889448874"],
    )
    add(
        "exact_liyakat_email",
        "What email address is on Liyakat's resume?",
        "exact_identifier",
        True,
        [span(pages, "Liyakat_DataScientist_Resume.pdf", 1, "liyakatakhoon@gmail.com")],
        ["liyakatakhoon@gmail.com"],
    )
    add(
        "paraphrase_internship",
        "Which organization hosted Liyakat's data science internship?",
        "paraphrase",
        True,
        [GoldItem("Liyakat_DataScientist_Resume.pdf", 1, "internship experience at Sabudh Foundation")],
        ["Sabudh Foundation"],
        notes="span may have hyphenation in PDF; verify visually",
    )
    add(
        "number_cgpa",
        "What CGPA is reported for the IUST B.Tech degree?",
        "number_or_date",
        True,
        [span(pages, "Liyakat_Hussain_DataScientist_Resume.pdf", 2, "CGPA: 7.8/10")],
        ["7.8"],
    )
    add(
        "factual_education_iust",
        "Which university is listed under Education?",
        "factual",
        True,
        [span(pages, "Liyakat_Hussain_DataScientist_Resume.pdf", 2, "Islamic University of Science and Technology (IUST), Kashmir")],
        ["IUST"],
    )
    add(
        "paraphrase_skills_python",
        "Does the technical skills section mention Python?",
        "paraphrase",
        True,
        [span(pages, "Liyakat_DataScientist_Resume.pdf", 2, "Programming Languages: Python, SQL, C, C++")],
        ["Python"],
    )
    add(
        "multi_document_resume_vs_hussain",
        "Across both Liyakat resume PDFs, what internship employer is shared?",
        "multi_document",
        True,
        [
            GoldItem("Liyakat_DataScientist_Resume.pdf", 1, "Sabudh Foundation"),
            GoldItem("Liyakat_Hussain_DataScientist_Resume.pdf", 1, "Sabudh Foundation"),
        ],
        ["Sabudh Foundation"],
    )
    add(
        "factual_mlops_tools",
        "Which MLOps tools are listed on the Hussain resume skills page?",
        "factual",
        True,
        [span(pages, "Liyakat_Hussain_DataScientist_Resume.pdf", 2, "MLOps & Deployment: MLflow, DagsHub, BentoML, Docker, AWS, Azure")],
        ["MLflow", "Docker"],
    )

    # ---- deepfake doc ----
    add(
        "factual_deepfake_title",
        "What is the title of the deepfake study document?",
        "factual",
        True,
        [span(pages, "deepfake_documentation.pdf", 1, "Deepfake Detection System")],
        ["Deepfake Detection System"],
    )
    add(
        "paraphrase_deepfake_def",
        "According to the introduction, what does the term deepfake refer to?",
        "paraphrase",
        True,
        [GoldItem(
            "deepfake_documentation.pdf",
            2,
            'refers to media that has been synthetically altered using deep neural networks',
        )],
        ["deep neural networks", "synthetically"],
        notes="Verify exact hyphenation/spacing on page 2",
    )
    add(
        "factual_gan_mention",
        "Which generative technique is listed as used for deepfake generation?",
        "factual",
        True,
        [GoldItem("deepfake_documentation.pdf", 2, "Generative Adversarial Networks (GANs)")],
        ["GANs"],
    )
    add(
        "factual_dang_dataset",
        "What dataset did Dang et al. introduce according to the literature survey?",
        "factual",
        True,
        [GoldItem("deepfake_documentation.pdf", 3, "Diverse Fake Face Dataset (DFFD)")],
        ["DFFD"],
    )
    add(
        "multi_hop_deepfake_video",
        "Why is video deepfake detection described as more complex than image deepfakes?",
        "multi_hop",
        True,
        [GoldItem(
            "deepfake_documentation.pdf",
            4,
            "making the detection process more complex due to the presence of temporal information",
        )],
        ["temporal"],
    )

    # ---- MediAssist ----
    add(
        "factual_mediassist_title",
        "What is the full project title of MediAssist?",
        "factual",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "MediAssist (Smart Medical Diagnosis Assistant)")],
        ["Smart Medical Diagnosis Assistant"],
    )
    add(
        "exact_student_id_faizan",
        "What is Faizan Bashir Bhat's student ID on the title page?",
        "exact_identifier",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Faizan Bashir Bhat (220302)")],
        ["220302"],
    )
    add(
        "exact_student_id_sakib",
        "What student ID is listed for Sakib Yousuf?",
        "exact_identifier",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Sakib Yousuf (220321)")],
        ["220321"],
    )
    add(
        "factual_supervisor",
        "Who supervised the MediAssist project?",
        "factual",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Ms. Aasia Quyoum")],
        ["Aasia Quyoum"],
    )
    add(
        "number_or_date_report_month",
        "In which month and year is the MediAssist report dated on the title page?",
        "number_or_date",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "October 2026")],
        ["October 2026"],
    )
    add(
        "paraphrase_college",
        "Which college department submitted the MediAssist report?",
        "paraphrase",
        True,
        [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Department of Computer Science and Engineering")],
        ["Computer Science"],
    )
    add(
        "factual_reranker_model",
        "Which cross-encoder model is named for MediAssist re-ranking?",
        "factual",
        True,
        [GoldItem(
            "MediAssist_Project_Report_final-version_2.pdf",
            31,
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )],
        ["ms-marco-MiniLM-L-6-v2"],
        notes="Confirm page number after extraction; PDF page index may differ from printed page",
    )
    add(
        "table_frontend_modules",
        "According to Table 4.1, what is the responsibility of pages/Chat.tsx?",
        "table",
        True,
        [GoldItem(
            "MediAssist_Project_Report_final-version_2.pdf",
            51,
            "pages/Chat.tsx Main screen; gates the follow-up questions before sending.",
        )],
        ["Chat.tsx", "follow-up"],
    )
    add(
        "multi_hop_mediassist_pipeline",
        "How does MediAssist combine bi-encoder and cross-encoder retrieval stages?",
        "multi_hop",
        True,
        [GoldItem(
            "MediAssist_Project_Report_final-version_2.pdf",
            21,
            "a fast bi-encoder finds a handful of candidates and a cross-encoder re-ranks only those",
        )],
        ["bi-encoder", "cross-encoder"],
    )
    add(
        "ambiguous_mediassist_authors",
        "Who wrote MediAssist?",
        "ambiguous",
        True,
        [
            span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Faizan Bashir Bhat (220302)"),
            span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Sakib Yousuf (220321)"),
            span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Fayiq Riyaz Khan (220309)"),
        ],
        ["Faizan", "Sakib", "Fayiq"],
        notes="Ambiguous because multiple authors; a good answer lists all three",
    )

    # ---- unanswerable out of domain (no gold spans) ----
    ood = [
        ("ood_mars_capital", "What is the capital of Mars colony Zeta-9?"),
        ("ood_tesla_revenue", "What was Tesla's Q3 2019 automotive revenue in USD?"),
        ("ood_flux_capacitor", "Who invented the DocuMind flux capacitor in 1847?"),
        ("ood_nobel_2021", "Who won the Nobel Prize in Literature in 2021 according to these PDFs?"),
        ("ood_bitcoin_price", "What was the Bitcoin closing price on 1 January 2015?"),
        ("ood_recipe", "How many cups of flour are in the chocolate cake recipe?"),
        ("ood_cricket", "What was India's score in the 2011 World Cup final?"),
        ("ood_movie", "Who directed the film Inception according to the indexed documents?"),
    ]
    for qid, query in ood:
        add(qid, query, "unanswerable_out_of_domain", False, [], [], notes="Topic absent from corpus")

    # ---- unanswerable near-miss (related topic exists, specific fact does not) ----
    near = [
        (
            "near_remote_stipend",
            "What is the remote-work stipend amount in the Acme leave policy?",
            "Policy says stipend is not defined",
        ),
        (
            "near_tesla_in_invoice",
            "What Tesla revenue figure appears on invoice INV-2023-Q3-0091?",
            "Invoice explicitly says it contains no Tesla revenue",
        ),
        (
            "near_http_418",
            "What does HTTP status code 418 mean in the DMAPI error reference?",
            "Doc only covers DMAPI codes, not general HTTP codes",
        ),
        (
            "near_liyakat_salary",
            "What was Liyakat Hussain's monthly internship stipend at Sabudh Foundation?",
            "Internship mentioned; stipend not stated",
        ),
        (
            "near_mediassist_accuracy",
            "What is MediAssist's reported clinical diagnostic accuracy percentage on a hospital trial?",
            "Architecture discussed; this specific trial metric not asserted in gold drafts",
        ),
        (
            "near_deepfake_gpu_hours",
            "How many GPU-hours were used to train the authors' final deepfake detector?",
            "Survey/doc discusses methods; training hours for authors' model not specified",
        ),
        (
            "near_ada_birth_year",
            "In which year was Ada Lovelace born according to the smoke resume?",
            "Smoke resume lists skill/experience only",
        ),
        (
            "near_parental_pay",
            "What percentage of salary is paid during Acme parental leave?",
            "Parental leave length given; pay percentage not given",
        ),
        (
            "near_dmapi_401",
            "What is the meaning of DMAPI-401 Unauthorized?",
            "4041/4290/5007 listed; 401 not listed",
        ),
        (
            "near_grace_award",
            "Which presidential medal did Grace Hopper receive according to the performance resume?",
            "Only name/skill/project listed",
        ),
    ]
    for qid, query, note in near:
        add(qid, query, "unanswerable_near_miss", False, [], [], notes=note)

    # Extra answerable fillers for category balance / ~70 total
    extras = [
        (
            "paraphrase_parental_leave",
            "How long is parental leave for primary caregivers at Acme?",
            "paraphrase",
            [span(pages, "policy_leave_entitlement.pdf", 1, "Parental leave: 26 weeks for primary caregivers.")],
            ["26 weeks"],
        ),
        (
            "number_invoice_tax",
            "How much tax is charged on the Q3 invoice fixture?",
            "number_or_date",
            [span(pages, "invoice_fixture_q3.pdf", 1, "Tax (8%): 111.20.")],
            ["111.20"],
        ),
        (
            "factual_invoice_vendor",
            "Who is the vendor on the internal invoice fixture?",
            "factual",
            [span(pages, "invoice_fixture_q3.pdf", 1, "Vendor: Northwind Supplies.")],
            ["Northwind Supplies"],
        ),
        (
            "paraphrase_univac",
            "What project is listed under Grace Hopper's performance resume?",
            "paraphrase",
            [span(pages, "_smoke_perf.pdf", 1, "Project: UNIVAC")],
            ["UNIVAC"],
        ),
        (
            "factual_hybrid_topic",
            "What topic does the QA design review document cover?",
            "factual",
            [span(pages, "qa_design.pdf", 1, "Topic: Hybrid retrieval")],
            ["Hybrid retrieval"],
        ),
        (
            "number_effective_date",
            "What is the effective date of the Acme leave policy?",
            "number_or_date",
            [span(pages, "policy_leave_entitlement.pdf", 1, "Effective date: 2024-01-15.")],
            ["2024-01-15"],
        ),
        (
            "exact_dmapi_4041",
            "What does DMAPI-4041 signify?",
            "exact_identifier",
            [span(pages, "api_error_codes.pdf", 1, "DMAPI-4041 NotFound: requested resource identifier was not found.")],
            ["NotFound"],
        ),
        (
            "table_sick_remaining",
            "For EMP-4412, how many sick leave days remain?",
            "table",
            [span(pages, "policy_leave_entitlement.pdf", 1, "Sick | 12 | 2 | 10")],
            ["10"],
        ),
        (
            "factual_fayiq_id",
            "What is Fayiq Riyaz Khan's ID on the MediAssist title page?",
            "exact_identifier",
            [span(pages, "MediAssist_Project_Report_final-version_2.pdf", 1, "Fayiq Riyaz Khan (220309)")],
            ["220309"],
        ),
        (
            "paraphrase_ada_experience",
            "What experience line is written for Ada Lovelace in the smoke test resume?",
            "paraphrase",
            [span(pages, "smoke_ada2.pdf", 1, "Experience: Computing pioneer at Analytical Engine project.")],
            ["Analytical Engine"],
        ),
        (
            "multi_document_names_ada_grace",
            "Which two historical computing figures appear as candidates across the smoke resumes?",
            "multi_document",
            [
                span(pages, "smoke_ada2.pdf", 1, "Candidate: Ada Lovelace"),
                span(pages, "_smoke_perf.pdf", 1, "Name: Grace Hopper"),
            ],
            ["Ada Lovelace", "Grace Hopper"],
        ),
        (
            "ambiguous_leave_days",
            "How many leave days does an Acme employee get?",
            "ambiguous",
            [
                span(pages, "policy_leave_entitlement.pdf", 1, "Annual paid leave entitlement for full-time employees is 18 days."),
                span(pages, "policy_leave_entitlement.pdf", 1, "Sick leave entitlement is 12 days per calendar year."),
            ],
            ["18", "12"],
            "Ambiguous without leave type",
        ),
    ]
    for item in extras:
        if len(item) == 6:
            qid, query, cat, gold, facts, notes = item
        else:
            qid, query, cat, gold, facts = item
            notes = ""
        add(qid, query, cat, True, gold, facts, notes)

    # Stratified tune/test ~30/70 by category
    by_cat: dict[str, list[Question]] = {}
    for q in qs:
        by_cat.setdefault(q.category, []).append(q)
    rng = random.Random(42)
    for cat, items in by_cat.items():
        rng.shuffle(items)
        n_tune = max(1, round(len(items) * 0.3)) if len(items) >= 3 else (1 if len(items) > 1 else 0)
        # ensure at least some tune overall
        for i, q in enumerate(items):
            q.split = "tune" if i < n_tune else "test"

    # If tune share too low, promote a few more
    n_tune = sum(1 for q in qs if q.split == "tune")
    target_tune = max(1, int(round(len(qs) * 0.3)))
    if n_tune < target_tune:
        for q in qs:
            if q.split == "test" and n_tune < target_tune:
                q.split = "tune"
                n_tune += 1

    write_questions(OUT, qs)
    from collections import Counter

    print(f"wrote {len(qs)} questions → {OUT}")
    print("split", Counter(q.split for q in qs))
    print("category", Counter(q.category for q in qs))
    print("answerable", sum(1 for q in qs if q.answerable), "unanswerable", sum(1 for q in qs if not q.answerable))
    print("near_miss", sum(1 for q in qs if q.category == "unanswerable_near_miss"))
    print("label_source", Counter(q.label_source for q in qs))


if __name__ == "__main__":
    main()
