"""Rebuild questions.jsonl for the public/fixture-only corpus (~70 drafts)."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from evals.schema import GoldItem, Question, write_questions
from evals.span_map import normalize_text

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
OUT = Path(__file__).resolve().parent / "questions.jsonl"


def extract_all() -> dict[str, list[str]]:
    from backend.app.rag.ingest import load_pdf

    out: dict[str, list[str]] = {}
    for pdf in sorted(CORPUS.glob("*.pdf")):
        pages = load_pdf(pdf)
        out[pdf.name] = [p.page_content for p in pages]
    return out


def find_span(pages: dict[str, list[str]], filename: str, needle: str) -> GoldItem:
    texts = pages[filename]
    for i, text in enumerate(texts, start=1):
        idx = text.find(needle)
        if idx >= 0:
            return GoldItem(filename=filename, page=i, span=text[idx : idx + len(needle)])
        # collapsed whitespace fallback — still store needle if present normalised
        if normalize_text(needle) in normalize_text(text):
            return GoldItem(filename=filename, page=i, span=needle)
    raise ValueError(f"cannot find {needle!r} in {filename}")


def main() -> None:
    pages = extract_all()
    assert set(pages) >= {
        "policy_leave_entitlement.pdf",
        "invoice_fixture_q3.pdf",
        "api_error_codes.pdf",
        "qa_design.pdf",
        "smoke_ada2.pdf",
        "_smoke_perf.pdf",
    }, f"missing fixtures: {sorted(pages)}"

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
                split="test",
                label_source="draft",
                notes=notes,
            )
        )

    S = lambda fn, needle: find_span(pages, fn, needle)

    # ---- answerable from fixtures ----
    add("factual_ada_name", "Who is the candidate named in the DocuMind smoke test resume?",
        "factual", True, [S("smoke_ada2.pdf", "Candidate: Ada Lovelace")], ["Ada Lovelace"])
    add("paraphrase_ada_skill", "What technical skill is listed for Ada in the smoke resume?",
        "paraphrase", True, [S("smoke_ada2.pdf", "Skill: Analytical Engine")], ["Analytical Engine"])
    add("paraphrase_ada_experience", "What experience line is written for Ada Lovelace?",
        "paraphrase", True,
        [S("smoke_ada2.pdf", "Experience: Computing pioneer at Analytical Engine project.")],
        ["Analytical Engine"])
    add("factual_grace_name", "What is the name on the performance resume?",
        "factual", True, [S("_smoke_perf.pdf", "Name: Grace Hopper")], ["Grace Hopper"])
    add("exact_grace_skill", "Which compiler skill is attributed to Grace Hopper?",
        "exact_identifier", True, [S("_smoke_perf.pdf", "Skill: COBOL Compiler")], ["COBOL Compiler"])
    add("paraphrase_univac", "What project is listed under Grace Hopper's performance resume?",
        "paraphrase", True, [S("_smoke_perf.pdf", "Project: UNIVAC")], ["UNIVAC"])
    add("factual_rrf", "What does Reciprocal Rank Fusion combine according to the QA design doc?",
        "factual", True,
        [S("qa_design.pdf", "Reciprocal Rank Fusion combines FAISS and BM25.")], ["FAISS", "BM25"])
    add("factual_hybrid_topic", "What topic does the QA design review document cover?",
        "factual", True, [S("qa_design.pdf", "Topic: Hybrid retrieval")], ["Hybrid retrieval"])

    add("number_annual_leave", "How many annual paid leave days do full-time employees get?",
        "number_or_date", True,
        [S("policy_leave_entitlement.pdf", "Annual paid leave entitlement for full-time employees is 18 days.")],
        ["18"])
    add("number_sick_leave", "What is the sick leave entitlement per calendar year?",
        "number_or_date", True,
        [S("policy_leave_entitlement.pdf", "Sick leave entitlement is 12 days per calendar year.")],
        ["12"])
    add("paraphrase_parental_leave", "How long is parental leave for primary caregivers at Acme?",
        "paraphrase", True,
        [S("policy_leave_entitlement.pdf", "Parental leave: 26 weeks for primary caregivers.")],
        ["26 weeks"])
    add("exact_policy_id", "What is the Policy ID for the Acme leave handbook?",
        "exact_identifier", True,
        [S("policy_leave_entitlement.pdf", "Policy ID: ACME-HR-LEAVE-2024.")], ["ACME-HR-LEAVE-2024"])
    add("number_effective_date", "What is the effective date of the Acme leave policy?",
        "number_or_date", True,
        [S("policy_leave_entitlement.pdf", "Effective date: 2024-01-15.")], ["2024-01-15"])
    add("exact_mgr_code", "What manager approval code is required for unpaid leave?",
        "exact_identifier", True,
        [S("policy_leave_entitlement.pdf", "manager approval code MGR-OK-77.")], ["MGR-OK-77"])
    add("table_emp_remaining_annual", "For employee EMP-4412, how many annual leave days remain?",
        "table", True, [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")], ["13", "EMP-4412"])
    add("table_sick_remaining", "For EMP-4412, how many sick leave days remain?",
        "table", True, [S("policy_leave_entitlement.pdf", "Sick | 12 | 2 | 10")], ["10"])
    add("table_annual_used", "How many annual leave days has EMP-4412 used?",
        "table", True, [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")], ["5"])
    add("ambiguous_leave_days", "How many leave days does an Acme employee get?",
        "ambiguous", True,
        [
            S("policy_leave_entitlement.pdf", "Annual paid leave entitlement for full-time employees is 18 days."),
            S("policy_leave_entitlement.pdf", "Sick leave entitlement is 12 days per calendar year."),
        ],
        ["18", "12"], "Ambiguous without leave type")

    add("number_invoice_total", "What is the total due on invoice INV-2023-Q3-0091?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Total due: 1501.20.")], ["1501.20"])
    add("number_invoice_tax", "How much tax is charged on the Q3 invoice fixture?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Tax (8%): 111.20.")], ["111.20"])
    add("number_invoice_subtotal", "What is the subtotal on the invoice fixture?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Subtotal: 1390.00.")], ["1390.00"])
    add("table_sku_b220_amount", "What is the line amount for SKU-B220?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-B220 Sensor kit Qty 10 Unit 89.00 Amount 890.00")],
        ["890.00", "SKU-B220"])
    add("table_sku_a100_qty", "What quantity was ordered for SKU-A100?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")],
        ["40", "SKU-A100"])
    add("exact_po_number", "What purchase order number is listed on the invoice fixture?",
        "exact_identifier", True, [S("invoice_fixture_q3.pdf", "Purchase order: PO-77821.")], ["PO-77821"])
    add("exact_invoice_id", "What is the invoice identifier on the fixture document?",
        "exact_identifier", True, [S("invoice_fixture_q3.pdf", "INV-2023-Q3-0091")], ["INV-2023-Q3-0091"])
    add("factual_invoice_vendor", "Who is the vendor on the internal invoice fixture?",
        "factual", True, [S("invoice_fixture_q3.pdf", "Vendor: Northwind Supplies.")], ["Northwind Supplies"])
    add("factual_invoice_customer", "Who is the customer on the invoice fixture?",
        "factual", True, [S("invoice_fixture_q3.pdf", "Customer: Contoso Labs.")], ["Contoso Labs"])
    add("number_invoice_date", "What is the invoice date on the fixture?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Invoice date: 2023-09-30.")], ["2023-09-30"])
    add("paraphrase_payment_terms", "What are the payment terms on the invoice?",
        "paraphrase", True, [S("invoice_fixture_q3.pdf", "Payment terms: Net 30.")], ["Net 30"])

    add("exact_dmapi_4290", "What does error code DMAPI-4290 mean?",
        "exact_identifier", True,
        [S("api_error_codes.pdf", "DMAPI-4290 RateLimited: client exceeded 60 requests per minute.")],
        ["RateLimited", "60"])
    add("exact_dmapi_4041", "What does DMAPI-4041 signify?",
        "exact_identifier", True,
        [S("api_error_codes.pdf", "DMAPI-4041 NotFound: requested resource identifier was not found.")],
        ["NotFound"])
    add("factual_dmapi_5007", "What does DMAPI-5007 indicate?",
        "factual", True,
        [S("api_error_codes.pdf", "DMAPI-5007 UpstreamTimeout: embedding provider timed out after 8s.")],
        ["UpstreamTimeout", "8s"])
    add("number_dmapi_retry", "How long should a client wait before retrying after DMAPI-4290?",
        "number_or_date", True,
        [S("api_error_codes.pdf", "for DMAPI-4290 wait 30 seconds then retry with jitter.")],
        ["30 seconds"])
    add("exact_dmapi_namespace", "What code namespace does the service error reference use?",
        "exact_identifier", True, [S("api_error_codes.pdf", "Code namespace: DMAPI.")], ["DMAPI"])
    add("factual_dmapi_version", "What document version is the error code reference?",
        "factual", True, [S("api_error_codes.pdf", "Document version 1.4.")], ["1.4"])
    add("exact_oncall", "What on-call alias is listed in the error code reference?",
        "exact_identifier", True,
        [S("api_error_codes.pdf", "documind-oncall@example.invalid")], ["documind-oncall@example.invalid"])

    add("multi_document_names_ada_grace",
        "Which two historical computing figures appear as candidates across the smoke resumes?",
        "multi_document", True,
        [S("smoke_ada2.pdf", "Candidate: Ada Lovelace"), S("_smoke_perf.pdf", "Name: Grace Hopper")],
        ["Ada Lovelace", "Grace Hopper"])
    add("multi_document_policy_and_invoice_currency_scope",
        "Does the leave policy or the invoice fixture mention USD?",
        "multi_document", True,
        [S("invoice_fixture_q3.pdf", "Currency: USD.")],
        ["USD"], "Policy does not; invoice does — multi-doc check")
    add("multi_hop_invoice_widgets_total",
        "Using the SKU-A100 line, what is qty times unit price?",
        "multi_hop", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")],
        ["500.00", "40", "12.50"])
    add("multi_hop_leave_remaining_math",
        "From the EMP-4412 annual leave row, does entitlement minus used equal remaining?",
        "multi_hop", True,
        [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")],
        ["18", "5", "13"])
    add("ambiguous_dmapi_timeout",
        "What timeout-related error is documented?",
        "ambiguous", True,
        [S("api_error_codes.pdf", "DMAPI-5007 UpstreamTimeout: embedding provider timed out after 8s.")],
        ["DMAPI-5007"], "Only one timeout code; still mildly ambiguous wording")

    # More paraphrases / factual variants for volume
    add("factual_policy_title", "What is the title of the Acme leave document?",
        "factual", True,
        [S("policy_leave_entitlement.pdf", "Acme Corp Employee Handbook - Leave Policy")],
        ["Leave Policy"])
    add("paraphrase_acme_sick", "How many sick days does Acme grant each year?",
        "paraphrase", True,
        [S("policy_leave_entitlement.pdf", "Sick leave entitlement is 12 days per calendar year.")],
        ["12"])
    add("factual_qa_title", "What is the title line of the QA design document?",
        "factual", True, [S("qa_design.pdf", "QA Design Review Doc")], ["QA Design Review"])
    add("paraphrase_ada_candidate_label", "How is Ada Lovelace labeled in the smoke resume header fields?",
        "paraphrase", True, [S("smoke_ada2.pdf", "Candidate: Ada Lovelace")], ["Ada Lovelace"])
    add("factual_smoke_title", "What is the title of the Ada smoke test resume?",
        "factual", True, [S("smoke_ada2.pdf", "DocuMind Smoke Test Resume")], ["DocuMind Smoke Test Resume"])
    add("factual_perf_title", "What is the title of the performance resume fixture?",
        "factual", True, [S("_smoke_perf.pdf", "Performance Resume")], ["Performance Resume"])
    add("number_tax_rate", "What tax rate is applied on the invoice fixture?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Tax (8%): 111.20.")], ["8%"])
    add("exact_sku_a100", "What is the SKU for the Widget pack line item?",
        "exact_identifier", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")],
        ["SKU-A100"])
    add("exact_emp_4412", "Which employee ID appears in the leave balance table?",
        "exact_identifier", True,
        [S("policy_leave_entitlement.pdf", "example employee EMP-4412")], ["EMP-4412"])
    add("paraphrase_rate_limit", "Which DMAPI code covers rate limiting?",
        "paraphrase", True,
        [S("api_error_codes.pdf", "DMAPI-4290 RateLimited: client exceeded 60 requests per minute.")],
        ["DMAPI-4290"])

    # ---- unanswerable OOD (8+) ----
    for qid, query in [
        ("ood_mars_capital", "What is the capital of Mars colony Zeta-9?"),
        ("ood_tesla_revenue", "What was Tesla's Q3 2019 automotive revenue in USD?"),
        ("ood_flux_capacitor", "Who invented the DocuMind flux capacitor in 1847?"),
        ("ood_nobel_2021", "Who won the Nobel Prize in Literature in 2021 according to these PDFs?"),
        ("ood_bitcoin_price", "What was the Bitcoin closing price on 1 January 2015?"),
        ("ood_recipe", "How many cups of flour are in the chocolate cake recipe?"),
        ("ood_cricket", "What was India's score in the 2011 World Cup final?"),
        ("ood_movie", "Who directed the film Inception according to the indexed documents?"),
        ("ood_olympics", "How many gold medals did Japan win at Tokyo 2020?"),
    ]:
        add(qid, query, "unanswerable_out_of_domain", False, [], [], "Topic absent from public corpus")

    # ---- near-miss (8+) ----
    for qid, query, note in [
        ("near_remote_stipend", "What is the remote-work stipend amount in the Acme leave policy?",
         "Doc says stipend is not defined"),
        ("near_tesla_in_invoice", "What Tesla revenue figure appears on invoice INV-2023-Q3-0091?",
         "Invoice says it contains no Tesla revenue"),
        ("near_http_418", "What does HTTP status code 418 mean in the DMAPI error reference?",
         "Only DMAPI codes listed"),
        ("near_dmapi_401", "What is the meaning of DMAPI-401 Unauthorized?",
         "4041/4290/5007 listed; 401 not listed"),
        ("near_ada_birth_year", "In which year was Ada Lovelace born according to the smoke resume?",
         "Smoke resume has no birth year"),
        ("near_parental_pay", "What percentage of salary is paid during Acme parental leave?",
         "Length given; pay % not given"),
        ("near_grace_award", "Which presidential medal did Grace Hopper receive according to the performance resume?",
         "Only name/skill/project listed"),
        ("near_invoice_iban", "What IBAN should be used to pay invoice INV-2023-Q3-0091?",
         "No bank details in fixture"),
        ("near_policy_pto_cashout", "Can unused Acme annual leave be cashed out at year end?",
         "Entitlements listed; cash-out rule absent"),
        ("near_rrf_alpha", "What alpha hyperparameter does the QA design doc set for RRF?",
         "Mentions RRF combining FAISS+BM25; no alpha value"),
    ]:
        add(qid, query, "unanswerable_near_miss", False, [], [], note)

    # Stratified tune/test ~30/70
    by_cat: dict[str, list[Question]] = {}
    for q in qs:
        by_cat.setdefault(q.category, []).append(q)
    rng = random.Random(42)
    for items in by_cat.values():
        rng.shuffle(items)
        n_tune = max(1, round(len(items) * 0.3)) if len(items) >= 3 else (1 if len(items) > 1 else 0)
        for i, q in enumerate(items):
            q.split = "tune" if i < n_tune else "test"
    n_tune = sum(1 for q in qs if q.split == "tune")
    target = max(1, int(round(len(qs) * 0.3)))
    for q in qs:
        if n_tune >= target:
            break
        if q.split == "test":
            q.split = "tune"
            n_tune += 1

    write_questions(OUT, qs)
    print(f"wrote {len(qs)} → {OUT}")
    print("split", dict(Counter(q.split for q in qs)))
    print("category", dict(Counter(q.category for q in qs)))
    print(
        "answerable", sum(1 for q in qs if q.answerable),
        "unanswerable", sum(1 for q in qs if not q.answerable),
        "near_miss", sum(1 for q in qs if q.category == "unanswerable_near_miss"),
        "ood", sum(1 for q in qs if q.category == "unanswerable_out_of_domain"),
    )


if __name__ == "__main__":
    main()
