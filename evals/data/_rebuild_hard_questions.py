"""Rebuild synthetic-corpus draft questions → questions_synthetic.jsonl (Phase 4 CI)."""

from __future__ import annotations

import random
import re
from collections import Counter
from pathlib import Path

from evals.difficulty import content_words, query_span_overlap
from evals.schema import GoldItem, Question, write_questions
from evals.span_map import normalize_text

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus" / "synthetic"
OUT = Path(__file__).resolve().parent / "questions_synthetic.jsonl"


def extract_all() -> dict[str, list[str]]:
    from backend.app.rag.ingest import load_pdf

    out: dict[str, list[str]] = {}
    for pdf in sorted(CORPUS.glob("*.pdf")):
        out[pdf.name] = [p.page_content for p in load_pdf(pdf)]
    return out


def find_span(pages: dict[str, list[str]], filename: str, needle: str) -> GoldItem:
    for i, text in enumerate(pages[filename], start=1):
        idx = text.find(needle)
        if idx >= 0:
            return GoldItem(filename=filename, page=i, span=text[idx : idx + len(needle)])
        if normalize_text(needle) in normalize_text(text):
            return GoldItem(filename=filename, page=i, span=needle)
    raise ValueError(f"cannot find {needle!r} in {filename}")


def main() -> None:
    pages = extract_all()
    qs: list[Question] = []

    def add(
        qid: str,
        query: str,
        category: str,
        answerable: bool,
        gold: list[GoldItem],
        key_facts: list[str],
        notes: str = "",
        *,
        max_overlap: float | None = None,
    ) -> None:
        if answerable and category == "paraphrase":
            ov = query_span_overlap(query, [g.span for g in gold])
            if ov is not None and ov > 0.30:
                raise ValueError(f"paraphrase overlap {ov:.2f} > 0.30 for {qid}: {query!r}")
        if max_overlap is not None and answerable:
            ov = query_span_overlap(query, [g.span for g in gold])
            if ov is not None and ov > max_overlap:
                raise ValueError(f"overlap {ov:.2f} > {max_overlap} for {qid}")
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

    # ----- keep / refresh core fixture questions -----
    add("factual_ada_name", "Who is the candidate on the DocuMind smoke test resume?",
        "factual", True, [S("smoke_ada2.pdf", "Candidate: Ada Lovelace")], ["Ada Lovelace"])
    add("paraphrase_ada_skill", "Which engineering construct is listed as Ada's specialty on the smoke resume?",
        "paraphrase", True, [S("smoke_ada2.pdf", "Skill: Analytical Engine")], ["Analytical Engine"])
    add("factual_grace_name", "What name appears on the performance resume fixture?",
        "factual", True, [S("_smoke_perf.pdf", "Name: Grace Hopper")], ["Grace Hopper"])
    add("exact_grace_skill", "Which compiler skill is attributed to Grace Hopper?",
        "exact_identifier", True, [S("_smoke_perf.pdf", "Skill: COBOL Compiler")], ["COBOL Compiler"])
    add("factual_rrf", "What two indexes does Reciprocal Rank Fusion combine in the QA design note?",
        "factual", True, [S("qa_design.pdf", "Reciprocal Rank Fusion combines FAISS and BM25.")], ["FAISS", "BM25"])
    add("paraphrase_hybrid_topic", "What retrieval theme does the QA design review discuss?",
        "paraphrase", True, [S("qa_design.pdf", "Topic: Hybrid retrieval")], ["Hybrid retrieval"])

    add("number_annual_leave", "How many annual paid leave days do Acme full-time employees receive?",
        "number_or_date", True,
        [S("policy_leave_entitlement.pdf", "Annual paid leave entitlement for full-time employees is 18 days.")], ["18"])
    add("number_sick_leave", "What sick-leave entitlement does Acme grant per calendar year?",
        "number_or_date", True,
        [S("policy_leave_entitlement.pdf", "Sick leave entitlement is 12 days per calendar year.")], ["12"])
    add("paraphrase_parental", "At Acme, what duration of family bonding time off applies to the main caregiver?",
        "paraphrase", True,
        [S("policy_leave_entitlement.pdf", "Parental leave: 26 weeks for primary caregivers.")], ["26 weeks"])
    add("exact_policy_id", "What is Policy ID ACME-HR-LEAVE-2024 attached to?",
        "exact_identifier", True,
        [S("policy_leave_entitlement.pdf", "Policy ID: ACME-HR-LEAVE-2024.")], ["ACME-HR-LEAVE-2024"],
        notes="Query includes ID; still exact_identifier category")
    add("table_emp_remaining_annual", "In the EMP-4412 leave table, what is remaining annual leave?",
        "table", True, [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")], ["13"])
    add("table_sick_remaining", "In the EMP-4412 leave table, what is remaining sick leave?",
        "table", True, [S("policy_leave_entitlement.pdf", "Sick | 12 | 2 | 10")], ["10"])
    add("table_annual_used", "In the EMP-4412 leave table, how many annual days were used?",
        "table", True, [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")], ["5"])
    add("table_sick_entitlement_row", "What entitlement value is shown on the sick row for EMP-4412?",
        "table", True, [S("policy_leave_entitlement.pdf", "Sick | 12 | 2 | 10")], ["12"])
    add("exact_mgr_code", "What manager approval code is required for unpaid leave at Acme?",
        "exact_identifier", True,
        [S("policy_leave_entitlement.pdf", "manager approval code MGR-OK-77.")], ["MGR-OK-77"])

    add("number_invoice_total", "What total is due on invoice INV-2023-Q3-0091?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Total due: 1501.20.")], ["1501.20"])
    add("table_sku_b220", "What line amount is shown for SKU-B220 on the invoice fixture?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-B220 Sensor kit Qty 10 Unit 89.00 Amount 890.00")], ["890.00"])
    add("table_sku_a100_qty", "What quantity is listed for SKU-A100 on the invoice fixture?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")], ["40"])
    add("table_sku_a100_amount", "What amount is listed for SKU-A100 on the invoice fixture?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")], ["500.00"])
    add("exact_po", "What purchase order number appears on the invoice fixture?",
        "exact_identifier", True, [S("invoice_fixture_q3.pdf", "Purchase order: PO-77821.")], ["PO-77821"])
    add("number_tax", "How much tax is charged on the Q3 invoice fixture?",
        "number_or_date", True, [S("invoice_fixture_q3.pdf", "Tax (8%): 111.20.")], ["111.20"])

    add("exact_dmapi_4290", "What does error code DMAPI-4290 mean?",
        "exact_identifier", True,
        [S("api_error_codes.pdf", "DMAPI-4290 RateLimited: client exceeded 60 requests per minute.")],
        ["RateLimited"])
    add("exact_dmapi_4041", "What does DMAPI-4041 signify?",
        "exact_identifier", True,
        [S("api_error_codes.pdf", "DMAPI-4041 NotFound: requested resource identifier was not found.")],
        ["NotFound"])
    add("number_dmapi_retry", "After DMAPI-4290, how many seconds should a client wait before retrying?",
        "number_or_date", True,
        [S("api_error_codes.pdf", "for DMAPI-4290 wait 30 seconds then retry with jitter.")], ["30"])
    add("factual_dmapi_5007", "What condition does DMAPI-5007 describe?",
        "factual", True,
        [S("api_error_codes.pdf", "DMAPI-5007 UpstreamTimeout: embedding provider timed out after 8s.")],
        ["UpstreamTimeout"])

    # ----- fund disambiguation (≥25% of answerable name a specific scheme) -----
    fund_qs = [
        ("disamb_amgf_ter", "In the Aurora Midcap Growth Fund SID, what is the Total Expense Ratio (TER)?",
         "scheme_amgf.pdf", "Total Expense Ratio (TER): 1.85%", ["1.85%"], "number_or_date"),
        ("disamb_amgf_d_ter", "In the Aurora Midcap Growth Fund - Direct SID, what is the TER?",
         "scheme_amgf_d.pdf", "Total Expense Ratio (TER): 0.95%", ["0.95%"], "number_or_date"),
        ("disamb_bfcf_ter", "According to the Boreal Flexi Cap Fund scheme document, what TER is stated?",
         "scheme_bfcf.pdf", "Total Expense Ratio (TER): 1.60%", ["1.60%"], "number_or_date"),
        ("disamb_bfcf_d_ter", "According to the Boreal Flexi Cap Fund - Direct scheme document, what TER is stated?",
         "scheme_bfcf_d.pdf", "Total Expense Ratio (TER): 0.72%", ["0.72%"], "number_or_date"),
        ("disamb_cldf_ter", "What TER does the Cascade Low Duration Fund SID list?",
         "scheme_cldf.pdf", "Total Expense Ratio (TER): 0.45%", ["0.45%"], "number_or_date"),
        ("disamb_cldf_d_ter", "What TER does the Cascade Low Duration Fund - Direct SID list?",
         "scheme_cldf_d.pdf", "Total Expense Ratio (TER): 0.22%", ["0.22%"], "number_or_date"),
        ("disamb_amgf_isin", "What ISIN is printed in the Aurora Midcap Growth Fund SID?",
         "scheme_amgf.pdf", "ISIN: INF0AUD00001", ["INF0AUD00001"], "exact_identifier"),
        ("disamb_amgf_d_isin", "What ISIN is printed in the Aurora Midcap Growth Fund - Direct SID?",
         "scheme_amgf_d.pdf", "ISIN: INF0AUD00002", ["INF0AUD00002"], "exact_identifier"),
        ("disamb_bfcf_isin", "What ISIN appears in the Boreal Flexi Cap Fund SID?",
         "scheme_bfcf.pdf", "ISIN: INF0BOR00011", ["INF0BOR00011"], "exact_identifier"),
        ("disamb_bfcf_d_isin", "What ISIN appears in the Boreal Flexi Cap Fund - Direct SID?",
         "scheme_bfcf_d.pdf", "ISIN: INF0BOR00012", ["INF0BOR00012"], "exact_identifier"),
        ("disamb_cldf_isin", "What ISIN is listed for Cascade Low Duration Fund?",
         "scheme_cldf.pdf", "ISIN: INF0CAS00021", ["INF0CAS00021"], "exact_identifier"),
        ("disamb_cldf_d_isin", "What ISIN is listed for Cascade Low Duration Fund - Direct?",
         "scheme_cldf_d.pdf", "ISIN: INF0CAS00022", ["INF0CAS00022"], "exact_identifier"),
        ("disamb_amgf_aum", "What AUM figure is stated in the Aurora Midcap Growth Fund SID?",
         "scheme_amgf.pdf", "Assets under management (AUM): INR 12,400 crore", ["12,400"], "number_or_date"),
        ("disamb_bfcf_aum", "What AUM figure is stated in the Boreal Flexi Cap Fund SID?",
         "scheme_bfcf.pdf", "Assets under management (AUM): INR 21,750 crore", ["21,750"], "number_or_date"),
        ("disamb_cldf_aum", "What AUM figure is stated in the Cascade Low Duration Fund SID?",
         "scheme_cldf.pdf", "Assets under management (AUM): INR 3,050 crore", ["3,050"], "number_or_date"),
        ("disamb_amgf_manager", "Who is the fund manager named in the Aurora Midcap Growth Fund SID?",
         "scheme_amgf.pdf", "Fund manager: Neha Kapoor", ["Neha Kapoor"], "factual"),
        ("disamb_bfcf_manager", "Who is the fund manager named in the Boreal Flexi Cap Fund SID?",
         "scheme_bfcf.pdf", "Fund manager: Arjun Mehta", ["Arjun Mehta"], "factual"),
        ("disamb_cldf_manager", "Who is the fund manager named in the Cascade Low Duration Fund SID?",
         "scheme_cldf.pdf", "Fund manager: Priya Nair", ["Priya Nair"], "factual"),
        ("disamb_amgf_exit", "What exit load rule is written in the Aurora Midcap Growth Fund SID?",
         "scheme_amgf.pdf", "Exit load: 1% if redeemed within 365 days", ["1%", "365"], "factual"),
        ("disamb_bfcf_exit", "What exit load rule is written in the Boreal Flexi Cap Fund SID?",
         "scheme_bfcf.pdf", "Exit load: Nil", ["Nil"], "factual"),
        ("disamb_amgf_code", "What scheme code does the Aurora Midcap Growth Fund SID use?",
         "scheme_amgf.pdf", "Scheme code: AMGF", ["AMGF"], "exact_identifier"),
        ("disamb_bfcf_code", "What scheme code does the Boreal Flexi Cap Fund SID use?",
         "scheme_bfcf.pdf", "Scheme code: BFCF", ["BFCF"], "exact_identifier"),
        ("disamb_cldf_risk", "What riskometer label is on the Cascade Low Duration Fund SID?",
         "scheme_cldf.pdf", "Riskometer: Low to Moderate", ["Low to Moderate"], "factual"),
        ("disamb_amgf_risk", "What riskometer label is on the Aurora Midcap Growth Fund SID?",
         "scheme_amgf.pdf", "Riskometer: Very High", ["Very High"], "factual"),
        ("disamb_amgf_d_aum", "What AUM is listed in the Aurora Midcap Growth Fund - Direct SID?",
         "scheme_amgf_d.pdf", "Assets under management (AUM): INR 8,100 crore", ["8,100"], "number_or_date"),
        ("disamb_bfcf_d_aum", "What AUM is listed in the Boreal Flexi Cap Fund - Direct SID?",
         "scheme_bfcf_d.pdf", "Assets under management (AUM): INR 14,200 crore", ["14,200"], "number_or_date"),
    ]
    for qid, query, fn, needle, facts, cat in fund_qs:
        add(qid, query, cat, True, [S(fn, needle)], facts,
            notes="disambiguation: query names specific scheme document")

    # multi_document (≥8)
    add("md_aurora_ters", "What TERs are stated for Aurora Midcap Growth Fund and its Direct plan?",
        "multi_document", True,
        [S("scheme_amgf.pdf", "Total Expense Ratio (TER): 1.85%"),
         S("scheme_amgf_d.pdf", "Total Expense Ratio (TER): 0.95%")],
        ["1.85%", "0.95%"])
    add("md_boreal_isins", "List the ISINs for Boreal Flexi Cap Fund regular and Direct SIDs.",
        "multi_document", True,
        [S("scheme_bfcf.pdf", "ISIN: INF0BOR00011"), S("scheme_bfcf_d.pdf", "ISIN: INF0BOR00012")],
        ["INF0BOR00011", "INF0BOR00012"])
    add("md_cascade_managers_same", "Do Cascade Low Duration Fund and its Direct plan name the same fund manager?",
        "multi_document", True,
        [S("scheme_cldf.pdf", "Fund manager: Priya Nair"), S("scheme_cldf_d.pdf", "Fund manager: Priya Nair")],
        ["Priya Nair"])
    add("md_ada_grace", "Which two computing figures appear across the smoke resume fixtures?",
        "multi_document", True,
        [S("smoke_ada2.pdf", "Candidate: Ada Lovelace"), S("_smoke_perf.pdf", "Name: Grace Hopper")],
        ["Ada Lovelace", "Grace Hopper"])
    add("md_circular_vs_sid", "Does circular REG-AMC-DISC-2024-07 itself publish Aurora's TER?",
        "multi_document", True,
        [S("circular_amc_disclosure_2024.pdf", "The circular does not name Aurora, Boreal or Cascade TER figures.")],
        ["does not name"], notes="expected: answer that circular does not set TER")
    add("md_amgf_bfcf_exit", "Compare exit loads in Aurora Midcap Growth Fund vs Boreal Flexi Cap Fund SIDs.",
        "multi_document", True,
        [S("scheme_amgf.pdf", "Exit load: 1% if redeemed within 365 days"),
         S("scheme_bfcf.pdf", "Exit load: Nil")],
        ["1%", "Nil"])
    add("md_cldf_plans_ter", "What TERs do Cascade Low Duration Fund and Cascade Low Duration Fund - Direct list?",
        "multi_document", True,
        [S("scheme_cldf.pdf", "Total Expense Ratio (TER): 0.45%"),
         S("scheme_cldf_d.pdf", "Total Expense Ratio (TER): 0.22%")],
        ["0.45%", "0.22%"])
    add("md_invoice_and_policy_currency", "Which fixture states Currency: USD — the invoice or the leave policy?",
        "multi_document", True,
        [S("invoice_fixture_q3.pdf", "Currency: USD.")], ["USD"],
        notes="expected: answer invoice; policy has no USD")

    # multi_hop (≥8)
    add("mh_amgf_gap", "Using Aurora Midcap Growth Fund SIDs, how does regular TER compare to Direct TER?",
        "multi_hop", True,
        [S("scheme_amgf.pdf", "Total Expense Ratio (TER): 1.85%"),
         S("scheme_amgf_d.pdf", "Total Expense Ratio (TER): 0.95%")],
        ["1.85%", "0.95%"], notes="expected: answer regular higher than direct")
    add("mh_invoice_widget_math", "On the invoice fixture, does SKU-A100 qty times unit price match the line amount?",
        "multi_hop", True,
        [S("invoice_fixture_q3.pdf", "SKU-A100 Widget pack Qty 40 Unit 12.50 Amount 500.00")],
        ["40", "12.50", "500.00"])
    add("mh_leave_math", "For EMP-4412 annual leave, does entitlement minus used equal remaining?",
        "multi_hop", True,
        [S("policy_leave_entitlement.pdf", "Annual | 18 | 5 | 13")], ["18", "5", "13"])
    add("mh_bfcf_gap", "Using Boreal Flexi Cap Fund SIDs, which plan has the lower TER?",
        "multi_hop", True,
        [S("scheme_bfcf.pdf", "Total Expense Ratio (TER): 1.60%"),
         S("scheme_bfcf_d.pdf", "Total Expense Ratio (TER): 0.72%")],
        ["0.72%", "Direct"])
    add("mh_note_points_sid", "The comparative note says not to mix TER values — where must an investor read Aurora's TER?",
        "multi_hop", True,
        [S("comparative_note_equity_schemes.pdf", "read each SID for TER and exit load rather than relying on this commentary.")],
        ["SID"], notes="expected: answer Aurora Midcap Growth Fund SID")
    add("mh_circular_ter_change", "Under circular REG-AMC-DISC-2024-07, when do TER changes need investor notice?",
        "multi_hop", True,
        [S("circular_amc_disclosure_2024.pdf", "Scheme-wise TER changes above 5 basis points require investor notice.")],
        ["5 basis points"])
    add("mh_cldf_not_equity", "Does the comparative note treat Cascade Low Duration Fund as an equity scheme?",
        "multi_hop", True,
        [S("comparative_note_equity_schemes.pdf", "Cascade Low Duration Fund is not an equity scheme.")],
        ["not an equity scheme"])
    add("mh_amgf_contact", "What contact domain is printed in the Aurora Midcap Growth Fund SID risks page?",
        "multi_hop", True,
        [S("scheme_amgf.pdf", "Contact: schemes@amgf.example.invalid")], ["amgf.example.invalid"])

    # ambiguous (≥5) with expected behaviour in notes
    add("amb_ter_aurora", "What is the TER of Aurora Midcap Growth Fund?",
        "ambiguous", True,
        [S("scheme_amgf.pdf", "Total Expense Ratio (TER): 1.85%"),
         S("scheme_amgf_d.pdf", "Total Expense Ratio (TER): 0.95%")],
        ["1.85%", "0.95%"],
        notes="expected_behaviour: weak_evidence or answer listing both regular and Direct")
    add("amb_leave_days", "How many leave days does an Acme employee get?",
        "ambiguous", True,
        [S("policy_leave_entitlement.pdf", "Annual paid leave entitlement for full-time employees is 18 days."),
         S("policy_leave_entitlement.pdf", "Sick leave entitlement is 12 days per calendar year.")],
        ["18", "12"],
        notes="expected_behaviour: answer distinguishing annual vs sick, or weak_evidence")
    add("amb_boreal_aum", "What is Boreal Flexi Cap Fund AUM?",
        "ambiguous", True,
        [S("scheme_bfcf.pdf", "Assets under management (AUM): INR 21,750 crore"),
         S("scheme_bfcf_d.pdf", "Assets under management (AUM): INR 14,200 crore")],
        ["21,750", "14,200"],
        notes="expected_behaviour: weak_evidence unless plan (regular/Direct) specified")
    add("amb_who_wrote_note", "Who should investors trust for TER — the comparative note or the SID?",
        "ambiguous", True,
        [S("comparative_note_equity_schemes.pdf", "read each SID for TER and exit load rather than relying on this commentary.")],
        ["SID"],
        notes="expected_behaviour: answer SID")
    add("amb_dmapi_timeout", "Which timeout-related error code is documented?",
        "ambiguous", True,
        [S("api_error_codes.pdf", "DMAPI-5007 UpstreamTimeout: embedding provider timed out after 8s.")],
        ["DMAPI-5007"],
        notes="expected_behaviour: answer DMAPI-5007")

    # paraphrase extras with strict overlap
    add("paraphrase_univac", "Which mid-20th-century computing system is credited on the performance resume?",
        "paraphrase", True, [S("_smoke_perf.pdf", "Project: UNIVAC")], ["UNIVAC"])
    add("paraphrase_circular_portfolio",
        "Under the 2024 AMC rule, within how many days after a month closes must holdings be made public?",
        "paraphrase", True,
        [S("circular_amc_disclosure_2024.pdf", "Monthly portfolio disclosure must be published within 10 days of month-end.")],
        ["10 days"])
    add("paraphrase_soft_closure",
        "Before pausing new subscriptions under REG-AMC-DISC-2024-07, how many business days of advance warning are mandated?",
        "paraphrase", True,
        [S("circular_amc_disclosure_2024.pdf", "Soft-closure of schemes requires 15 business days public notice.")],
        ["15 business days"])
    add("paraphrase_amgf_benchmark",
        "Which mid-size equity index does the Aurora Midcap Growth Fund SID cite as its reference?",
        "paraphrase", True,
        [S("scheme_amgf.pdf", "Benchmark: NIFTY Midcap 150 TRI (illustrative).")],
        ["NIFTY Midcap 150 TRI"])
    add("paraphrase_bfcf_objective",
        "What investment aim does the Boreal Flexi Cap Fund SID state for spanning firm sizes?",
        "paraphrase", True,
        [S("scheme_bfcf.pdf", "Investment objective: long-term capital appreciation across market caps.")],
        ["across market caps"])
    add("paraphrase_cldf_objective",
        "What return-and-safety aim does the Cascade Low Duration Fund SID describe?",
        "paraphrase", True,
        [S("scheme_cldf.pdf", "Investment objective: income with capital preservation over a low-duration horizon.")],
        ["income", "capital preservation"])

    # tables extras for ≥8
    add("table_invoice_tax_rate_row", "What tax percentage is shown beside the tax amount on the invoice?",
        "table", True, [S("invoice_fixture_q3.pdf", "Tax (8%): 111.20.")], ["8%"])
    add("table_sku_b220_qty", "What quantity is shown for SKU-B220?",
        "table", True,
        [S("invoice_fixture_q3.pdf", "SKU-B220 Sensor kit Qty 10 Unit 89.00 Amount 890.00")], ["10"])

    # ----- unanswerable (≥25, >half near-miss) -----
    ood = [
        ("ood_mars", "What is the capital of Mars colony Zeta-9?"),
        ("ood_tesla", "What was Tesla's Q3 2019 automotive revenue in USD?"),
        ("ood_nobel", "Who won the Nobel Prize in Literature in 2021 per these PDFs?"),
        ("ood_bitcoin", "What was Bitcoin's closing price on 1 January 2015?"),
        ("ood_recipe", "How many cups of flour are in the chocolate cake recipe?"),
        ("ood_cricket", "What was India's score in the 2011 World Cup final?"),
        ("ood_movie", "Who directed Inception according to the indexed documents?"),
        ("ood_olympics", "How many gold medals did Japan win at Tokyo 2020?"),
        ("ood_weather", "What was the rainfall in Mumbai on 12 July 2018?"),
        ("ood_ceo_apple", "Who is Apple's CFO according to these scheme documents?"),
    ]
    for qid, query in ood:
        add(qid, query, "unanswerable_out_of_domain", False, [], [], "absent from corpus")

    near = [
        ("near_amgf_sharpe", "What is the Sharpe ratio of Aurora Midcap Growth Fund?",
         "Field type (risk metrics) discussed elsewhere; Sharpe not in SID"),
        ("near_bfcf_alpha", "What is the alpha of Boreal Flexi Cap Fund versus NIFTY 500?",
         "Benchmark named; alpha not provided"),
        ("near_cldf_ytm", "What is the portfolio YTM of Cascade Low Duration Fund?",
         "Duration fund exists; YTM not stated"),
        ("near_amgf_d_exit_diff", "Does Aurora Midcap Growth Fund - Direct have a different exit load than regular?",
         "Both state same exit load text; question asks difference — near miss on 'different'"),
        ("near_aurora_ter_in_circular", "What TER does circular REG-AMC-DISC-2024-07 assign to Aurora?",
         "Circular explicitly does not name fund TERs"),
        ("near_note_amgf_ter", "What TER does comparative note CMP-NOTE-2024-11 list for Aurora Midcap Growth Fund?",
         "Note avoids numeric TER"),
        ("near_remote_stipend", "What remote-work stipend does the Acme leave policy define?",
         "Policy says stipend not defined"),
        ("near_tesla_invoice", "What Tesla revenue appears on invoice INV-2023-Q3-0091?",
         "Invoice says no Tesla revenue"),
        ("near_dmapi_401", "What does DMAPI-401 Unauthorized mean?",
         "Nearby codes exist; 401 absent"),
        ("near_http_418", "What does HTTP 418 mean in the DMAPI reference?",
         "Only DMAPI namespace codes"),
        ("near_ada_birth", "In which year was Ada Lovelace born per the smoke resume?",
         "Resume has no birth year"),
        ("near_grace_medal", "Which medal did Grace Hopper receive per the performance resume?",
         "Only name/skill/project"),
        ("near_parental_pay", "What salary percentage is paid during Acme parental leave?",
         "Duration given; pay % absent"),
        ("near_bfcf_isin_in_cascade", "What Boreal ISIN is printed in the Cascade Low Duration Fund SID?",
         "Wrong entity; ISIN field exists for Cascade only"),
        ("near_amgf_manager_priya", "Is Priya Nair the manager of Aurora Midcap Growth Fund?",
         "Priya manages Cascade; Aurora lists Neha Kapoor"),
        ("near_invoice_iban", "What IBAN should be used to pay INV-2023-Q3-0091?",
         "No bank details"),
        ("near_cldf_equity_allocation", "What equity allocation % does Cascade Low Duration Fund target?",
         "Not an equity scheme; allocation % absent"),
        ("near_second_fine", "What fine applies on a third REG-AMC-DISC-2024-07 violation?",
         "Only first/second instance described"),
    ]
    for qid, query, note in near:
        add(qid, query, "unanswerable_near_miss", False, [], [], note)

    # Stratify tune/test 30/70
    by_cat: dict[str, list[Question]] = {}
    for q in qs:
        by_cat.setdefault(q.category, []).append(q)
    rng = random.Random(7)
    for items in by_cat.values():
        rng.shuffle(items)
        n_tune = max(1, round(len(items) * 0.3)) if len(items) >= 3 else (1 if len(items) > 1 else 0)
        for i, q in enumerate(items):
            q.split = "tune" if i < n_tune else "test"

    # Stats / gates
    n = len(qs)
    n_ans = sum(1 for q in qs if q.answerable)
    n_disamb = sum(1 for q in qs if q.answerable and "disambiguation" in (q.notes or ""))
    n_unans = sum(1 for q in qs if not q.answerable)
    n_near = sum(1 for q in qs if q.category == "unanswerable_near_miss")
    assert n_disamb / max(1, n_ans) >= 0.25, f"disamb share {n_disamb}/{n_ans}"
    assert sum(1 for q in qs if q.category == "multi_document") >= 8
    assert sum(1 for q in qs if q.category == "multi_hop") >= 8
    assert sum(1 for q in qs if q.category == "table") >= 8
    assert sum(1 for q in qs if q.category == "ambiguous") >= 5
    assert n_unans >= 25
    assert n_near > n_unans / 2

    # paraphrase overlap report
    print("paraphrase overlaps:")
    for q in qs:
        if q.category == "paraphrase" and q.answerable:
            ov = query_span_overlap(q.query, [g.span for g in q.gold])
            print(f"  {q.id}: {ov:.3f}")
            assert ov is not None and ov <= 0.30

    write_questions(OUT, qs)
    print(f"wrote {n} questions → {OUT}")
    print("split", dict(Counter(q.split for q in qs)))
    print("category", dict(Counter(q.category for q in qs)))
    print(f"answerable={n_ans} unanswerable={n_unans} near={n_near} disamb={n_disamb} ({100*n_disamb/n_ans:.1f}%)")


if __name__ == "__main__":
    main()
