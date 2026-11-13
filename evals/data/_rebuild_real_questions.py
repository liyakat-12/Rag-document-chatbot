"""Rebuild ~100 draft questions against evals/corpus/real/ (primary corpus)."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from evals.difficulty import query_span_overlap
from evals.schema import GoldItem, Question, write_questions
from evals.span_map import normalize_text

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus" / "real"
OUT = Path(__file__).resolve().parent / "questions.jsonl"


def extract_all() -> dict[str, list[tuple[int, str]]]:
    """filename -> list of (page_number, text) using PDF metadata page numbers."""
    from backend.app.rag.ingest import load_pdf

    out: dict[str, list[tuple[int, str]]] = {}
    for pdf in sorted(CORPUS.glob("*.pdf")):
        pages = []
        for i, p in enumerate(load_pdf(pdf)):
            meta = p.metadata.get("page")
            page_no = int(meta) + 1 if isinstance(meta, int) else i + 1
            pages.append((page_no, p.page_content))
        out[pdf.name] = pages
    return out


def find_span(pages: dict[str, list[tuple[int, str]]], filename: str, needle: str) -> GoldItem:
    for page_no, text in pages[filename]:
        idx = text.find(needle)
        if idx >= 0:
            return GoldItem(filename=filename, page=page_no, span=text[idx : idx + len(needle)])
        if normalize_text(needle) in normalize_text(text):
            return GoldItem(filename=filename, page=page_no, span=needle)
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
    ) -> None:
        if answerable and category == "paraphrase":
            ov = query_span_overlap(query, [g.span for g in gold])
            if ov is not None and ov > 0.30:
                raise ValueError(f"paraphrase overlap {ov:.2f} > 0.30 for {qid}: {query!r}")
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

    H = "sid_hdfc_midcap.pdf"
    K = "sid_kotak_midcap.pdf"
    M = "sid_motilal_midcap.pdf"
    N = "sid_nippon_growth_midcap.pdf"
    P = "sid_ppfas_flexicap.pdf"
    MC = "sebi_mf_master_circular_2024-06.pdf"
    SC = "sebi_circular_commodity_overseas_fm_2024-04.pdf"

    # ----- disambiguation among similar midcap SIDs (≥25% of answerable) -----
    fund_qs = [
        ("disamb_hdfc_code", "In the HDFC Mid Cap Fund SID, what is the SEBI Scheme Code?",
         H, "SEBI Scheme Code HDFC/O/E/MIF/07/04/0015", ["HDFC/O/E/MIF/07/04/0015"], "exact_identifier"),
        ("disamb_kotak_code", "In the Kotak Midcap Fund SID, what scheme code is listed?",
         K, "Scheme code KOTM/O/E/MIF/06/09/0018", ["KOTM/O/E/MIF/06/09/0018"], "exact_identifier"),
        ("disamb_motilal_code", "In the Motilal Oswal Midcap Fund SID, what scheme code appears on the cover?",
         M, "Scheme code: - MOTO/O/E/MIF/14/01/0006", ["MOTO/O/E/MIF/14/01/0006"], "exact_identifier"),
        ("disamb_nippon_code", "In the Nippon India Growth Mid Cap Fund SID, what Scheme Code is printed?",
         N, "Scheme Code : NIMF/O/E/MIF/95/08/0001", ["NIMF/O/E/MIF/95/08/0001"], "exact_identifier"),
        ("disamb_ppfas_code", "In the Parag Parikh Flexi Cap Fund SID, what scheme code is stated?",
         P, "Scheme code PPFA/O/E/FCF/13/04/0001", ["PPFA/O/E/FCF/13/04/0001"], "exact_identifier"),
        ("disamb_hdfc_bench", "What AMFI Tier I benchmark does the HDFC Mid Cap Fund SID show on the cover?",
         H, "NIFTY MIDCAP 150 (TRI)", ["NIFTY MIDCAP 150"], "factual"),
        ("disamb_kotak_bench", "What Tier 1 benchmark does the Kotak Midcap Fund SID list?",
         K, "Tier 1: Nifty Midcap 150 TRI", ["Nifty Midcap 150 TRI"], "factual"),
        ("disamb_motilal_bench", "Which midcap total-return index is named as the Motilal Oswal Midcap Fund benchmark?",
         M, "Nifty Midcap 150 Total Return \nIndex)", ["Nifty Midcap 150"], "factual"),
        ("disamb_nippon_bench", "What AMFI Tier I benchmark is shown for Nippon India Growth Mid Cap Fund?",
         N, "NIFTY Midcap 150 TRI", ["NIFTY Midcap 150 TRI"], "factual"),
        ("disamb_ppfas_bench", "What AMFI Tier I benchmark riskometer pair does the Parag Parikh Flexi Cap Fund SID cite?",
         P, "Nifty 500 TRI", ["Nifty 500 TRI"], "factual"),
        ("disamb_hdfc_former", "What former name does the HDFC Mid Cap Fund SID give for the scheme?",
         H, "Formerly known as HDFC Mid-Cap Opportunities Fund", ["HDFC Mid-Cap Opportunities Fund"], "factual"),
        ("disamb_kotak_legal_name", "What legal scheme name appears in the Kotak Midcap Fund SID particulars table?",
         K, "Name of the scheme KOTAK EMERGING EQUITY FUND", ["KOTAK EMERGING EQUITY FUND"], "factual"),
        ("disamb_hdfc_exit", "What exit-load percentage does the HDFC Mid Cap Fund SID charge within 1 year?",
         H, "Exit Load \nof 1.00% is payable if Units are redeemed/ switched -out \nwithin 1 year from the date of allotment.",
         ["1.00%"], "number_or_date"),
        ("disamb_nippon_exit", "What exit load does the Nippon India Growth Mid Cap Fund SID apply within 1 month?",
         N, "1% if redeemed or switched out on or before completion of 1 month from the date of allotment of units.",
         ["1%", "1 month"], "number_or_date"),
        ("disamb_motilal_exit", "What exit load does the Motilal Oswal Midcap Fund SID apply on or before 365 days?",
         M, "1% - If redeemed on or before 365 days from the date of allotment.",
         ["1%", "365"], "number_or_date"),
        ("disamb_kotak_exit_nil_band", "In the Kotak Midcap Fund SID, what exit load applies for upto 10% redeemed within 1 year?",
         K, "For redemption / switch out of upto 10% of the initial investment \namount (limit) purchased or switched in within 1 year from the date \nof allotment: Nil.",
         ["Nil", "10%"], "number_or_date"),
        ("disamb_ppfas_horizon", "What minimum investment horizon does the Parag Parikh Flexi Cap Fund SID note for investors?",
         P, "investment horizon of minimum 5 years", ["5 years"], "number_or_date"),
        ("disamb_hdfc_obj", "What investment objective sentence does the HDFC Mid Cap Fund SID state?",
         H, "Investment Objective To provide long -term capital appreciation/income by investing \npredominantly in Mid-Cap companies.",
         ["Mid-Cap"], "factual"),
        ("disamb_motilal_obj", "What investment objective does the Motilal Oswal Midcap Fund SID state?",
         M, "Investment objective The investment objective of the Scheme is to achieve long term capital \nappreciation by investing in quality mid -cap companies having long-term \ncompetitive advantages and potential for growth.",
         ["mid -cap companies"], "factual"),
        ("disamb_nippon_obj", "What primary investment objective does the Nippon India Growth Mid Cap Fund SID state?",
         N, "Investment objective The primary investment objective of the Scheme is to achieve long term growth of capital by investing in equity \nand equity related securities through a research based investment approach.",
         ["long term growth of capital"], "factual"),
        ("disamb_ppfas_obj", "What investment objective opening does the Parag Parikh Flexi Cap Fund SID use?",
         P, "Investment objective The investment objective of the Scheme is to seek to generate long -\nterm capital growth from an actively managed portfolio primarily of \nEquity and Equity related securities.",
         ["long -\nterm capital growth"], "factual"),
        ("disamb_kotak_obj", "What investment objective does the Kotak Midcap Fund SID state for mid companies?",
         K, "The investment objective of the scheme is to generate long -term \ncapital appreciation from a portfolio of equity and equity related \nsecurities, by investing predominantly in mid companies.",
         ["mid companies"], "factual"),
        ("disamb_hdfc_type", "How does the HDFC Mid Cap Fund SID describe the scheme type on the cover?",
         H, "An open ended equity scheme predominantly investing in mid cap stocks",
         ["mid cap stocks"], "factual"),
        ("disamb_ppfas_type", "How does the Parag Parikh Flexi Cap Fund SID describe the scheme type?",
         P, "An open-ended dynamic equity scheme investing  \nacross large cap, mid cap, small cap stocks.",
         ["flexi", "large cap"], "factual"),
        ("disamb_nippon_name", "What full scheme name appears with the Scheme Code on the Nippon India Growth Mid Cap Fund SID cover?",
         N, "Nippon India Growth Mid Cap Fund", ["Nippon India Growth Mid Cap Fund"], "factual"),
        ("disamb_motilal_name", "What scheme title heads the Motilal Oswal Midcap Fund SID?",
         M, "MOTILAL OSWAL MIDCAP FUND", ["MOTILAL OSWAL MIDCAP FUND"], "exact_identifier"),
    ]
    for qid, query, fn, needle, facts, cat in fund_qs:
        add(qid, query, cat, True, [S(fn, needle)], facts,
            notes="disambiguation: query names specific scheme document")

    # factual / identifiers on circulars
    add("exact_master_id", "What circular ID and date open the SEBI Master Circular for Mutual Funds PDF?",
        "exact_identifier", True,
        [S(MC, "SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90 June 27, 2024")],
        ["SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90", "June 27, 2024"])
    add("factual_master_supersede", "Which prior master circular does the June 2024 SEBI Mutual Funds Master Circular supersede?",
        "factual", True,
        [S(MC, "supersedes the Master Circular for Mutual Funds dated May 19, 2023")],
        ["May 19, 2023"])
    add("exact_commodity_circular_id", "What is the circular number of the April 2024 SEBI ease-of-doing-business fund-manager circular?",
        "exact_identifier", True,
        [S(SC, "SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 April 30, 2024")],
        ["SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30"])
    add("factual_commodity_optional", "Per the April 2024 SEBI circular, is a dedicated fund manager mandatory for Gold/Silver ETFs?",
        "factual", True,
        [S(SC, "dedicated fund manager shall be optional")],
        ["optional"])

    # multi_document (≥8)
    add("md_midcap_codes", "List the SEBI/scheme codes from the HDFC Mid Cap and Motilal Oswal Midcap SIDs.",
        "multi_document", True,
        [S(H, "HDFC/O/E/MIF/07/04/0015"), S(M, "MOTO/O/E/MIF/14/01/0006")],
        ["HDFC/O/E/MIF/07/04/0015", "MOTO/O/E/MIF/14/01/0006"])
    add("md_kotak_nippon_codes", "What scheme codes appear in the Kotak Midcap and Nippon India Growth Mid Cap SIDs?",
        "multi_document", True,
        [S(K, "KOTM/O/E/MIF/06/09/0018"), S(N, "NIMF/O/E/MIF/95/08/0001")],
        ["KOTM/O/E/MIF/06/09/0018", "NIMF/O/E/MIF/95/08/0001"])
    add("md_ppfas_vs_hdfc_bench", "Compare the Tier-I benchmarks named in Parag Parikh Flexi Cap vs HDFC Mid Cap SIDs.",
        "multi_document", True,
        [S(P, "Nifty 500 TRI"), S(H, "NIFTY MIDCAP 150 (TRI)")],
        ["Nifty 500 TRI", "NIFTY MIDCAP 150"])
    add("md_exit_hdfc_nippon", "Compare early-exit load rules in HDFC Mid Cap Fund vs Nippon India Growth Mid Cap Fund SIDs.",
        "multi_document", True,
        [S(H, "Exit Load \nof 1.00% is payable if Units are redeemed/ switched -out \nwithin 1 year from the date of allotment."),
         S(N, "1% if redeemed or switched out on or before completion of 1 month from the date of allotment of units.")],
        ["1.00%", "1 month"])
    add("md_circulars_ids", "What are the circular IDs of the June 2024 Master Circular and the April 2024 commodity/overseas FM circular?",
        "multi_document", True,
        [S(MC, "SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90"),
         S(SC, "SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30")],
        ["2024/90", "2024/30"])
    add("md_kotak_legal_vs_cover", "Does the Kotak Midcap Fund cover title match the legal name in its particulars table?",
        "multi_document", True,
        [S(K, "Kotak Midcap Fund"), S(K, "KOTAK EMERGING EQUITY FUND")],
        ["Kotak Midcap Fund", "KOTAK EMERGING EQUITY FUND"],
        notes="expected: answer they differ — cover vs legal name")
    add("md_four_midcap_names", "Which four mid-cap scheme SIDs are in the real corpus (HDFC, Kotak, Motilal, Nippon)?",
        "multi_document", True,
        [S(H, "HDFC Mid Cap Fund"), S(K, "Kotak Midcap Fund"),
         S(M, "MOTILAL OSWAL MIDCAP FUND"), S(N, "Nippon India Growth Mid Cap Fund")],
        ["HDFC", "Kotak", "Motilal", "Nippon"])
    add("md_master_vs_short", "Does the short April 2024 circular itself supersede the May 2023 Master Circular?",
        "multi_document", True,
        [S(MC, "supersedes the Master Circular for Mutual Funds dated May 19, 2023"),
         S(SC, "SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 April 30, 2024")],
        ["Master Circular"],
        notes="expected: answer no — supersession is in the Master Circular PDF")

    # multi_hop (≥8)
    add("mh_hdfc_former_to_code", "Using the HDFC Mid Cap Fund SID, what scheme code belongs to the fund formerly called Mid-Cap Opportunities?",
        "multi_hop", True,
        [S(H, "Formerly known as HDFC Mid-Cap Opportunities Fund"),
         S(H, "HDFC/O/E/MIF/07/04/0015")],
        ["HDFC/O/E/MIF/07/04/0015"])
    add("mh_nippon_exit_vs_hdfc", "Which SID imposes a 1% exit load for a shorter initial window — Nippon Growth Mid Cap or HDFC Mid Cap?",
        "multi_hop", True,
        [S(N, "1% if redeemed or switched out on or before completion of 1 month from the date of allotment of units."),
         S(H, "within 1 year from the date of allotment.")],
        ["Nippon", "1 month"])
    add("mh_ppfas_horizon_obj", "Does the Parag Parikh Flexi Cap Fund SID tie its 5-year horizon note to a long-term capital-growth objective?",
        "multi_hop", True,
        [S(P, "investment horizon of minimum 5 years"),
         S(P, "generate long -\nterm capital growth")],
        ["5 years", "capital growth"])
    add("mh_master_date_id", "Confirm the June 27, 2024 Master Circular ID that the Nippon SID cites via Clause 10.6 language context.",
        "multi_hop", True,
        [S(MC, "SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90 June 27, 2024"),
         S(N, "Pursuant to Clause 10.6 of SEBI Master circular dated June 27, 2024")],
        ["2024/90", "June 27, 2024"])
    add("mh_kotak_tier2", "Besides Tier 1 Nifty Midcap 150 TRI, what Tier 2 benchmark does the Kotak Midcap Fund SID list?",
        "multi_hop", True,
        [S(K, "Tier 1: Nifty Midcap 150 TRI"),
         S(K, "Tier 2:Nifty Midcap 100 TRI")],
        ["Nifty Midcap 100 TRI"])
    add("mh_commodity_gold_optional", "Under the April 2024 circular, for which ETF examples is a dedicated fund manager optional?",
        "multi_hop", True,
        [S(SC, "commodity based funds such as Gold ETFs, Silver ETFs"),
         S(SC, "dedicated fund manager shall be optional")],
        ["Gold ETFs", "Silver ETFs", "optional"])
    add("mh_motilal_365", "Does Motilal Oswal Midcap Fund charge exit load after 365 days according to its SID?",
        "multi_hop", True,
        [S(M, "1% - If redeemed on or before 365 days from the date of allotment."),
         S(M, "Nil - If redeemed after 365 days from the date of allotment.")],
        ["Nil"])
    add("mh_ppfas_not_midcap_only", "Is Parag Parikh Flexi Cap Fund described as mid-cap-only like the HDFC Mid Cap Fund SID?",
        "multi_hop", True,
        [S(P, "across large cap, mid cap, small cap stocks."),
         S(H, "predominantly investing in mid cap stocks")],
        ["large cap", "mid cap", "small cap"],
        notes="expected: answer no — flexi across caps")

    # ambiguous (≥5)
    add("amb_midcap_ter", "What is the TER of the midcap fund?",
        "ambiguous", True,
        [S(H, "HDFC Mid Cap Fund"), S(K, "Kotak Midcap Fund"), S(M, "MOTILAL OSWAL MIDCAP FUND")],
        ["ambiguous"],
        notes="expected_behaviour: weak_evidence or not_found without naming which SID")
    add("amb_exit_1pct", "Which scheme charges 1% exit load?",
        "ambiguous", True,
        [S(H, "Exit Load \nof 1.00% is payable"),
         S(N, "1% if redeemed or switched out on or before completion of 1 month"),
         S(M, "1% - If redeemed on or before 365 days")],
        ["1%"],
        notes="expected_behaviour: weak_evidence — multiple SIDs")
    add("amb_benchmark_midcap150", "What scheme uses Nifty Midcap 150 TRI as benchmark?",
        "ambiguous", True,
        [S(H, "NIFTY MIDCAP 150 (TRI)"), S(K, "Nifty Midcap 150 TRI"), S(N, "NIFTY Midcap 150 TRI")],
        ["Midcap 150"],
        notes="expected_behaviour: answer listing multiple midcap SIDs or weak_evidence")
    add("amb_master_circular_date", "What is the date of the SEBI mutual fund circular?",
        "ambiguous", True,
        [S(MC, "June 27, 2024"), S(SC, "April 30, 2024")],
        ["June 27, 2024", "April 30, 2024"],
        notes="expected_behaviour: weak_evidence — two circulars")
    add("amb_kotak_name", "What is the name of the Kotak midcap scheme?",
        "ambiguous", True,
        [S(K, "Kotak Midcap Fund"), S(K, "KOTAK EMERGING EQUITY FUND")],
        ["Kotak Midcap Fund", "KOTAK EMERGING EQUITY FUND"],
        notes="expected_behaviour: answer distinguishing cover vs legal name, or weak_evidence")

    # table-ish structured rows from SID particulars (≥8)
    add("table_hdfc_category_row", "In the HDFC Mid Cap Fund SID particulars, what category is listed with the scheme code row?",
        "table", True,
        [S(H, "SEBI Scheme Code HDFC/O/E/MIF/07/04/0015")],
        ["HDFC/O/E/MIF/07/04/0015"],
        notes="particulars table row")
    add("table_kotak_category", "In the Kotak Midcap Fund SID particulars table, what category text is shown?",
        "table", True,
        [S(K, "Category of the Scheme Equity Schemes – Midcap Fund")],
        ["Midcap Fund"])
    add("table_ppfas_scheme_code_row", "In the Parag Parikh Flexi Cap Fund SID particulars, which scheme code sits in the IV row?",
        "table", True,
        [S(P, "Scheme code PPFA/O/E/FCF/13/04/0001")],
        ["PPFA/O/E/FCF/13/04/0001"])
    add("table_nippon_load_row", "In the Nippon India Growth Mid Cap Fund SID load structure row, what 1-month exit load is stated?",
        "table", True,
        [S(N, "1% if redeemed or switched out on or before completion of 1 month from the date of allotment of units. Nil, \nthereafter.")],
        ["1%", "Nil"])
    add("table_motilal_load_row", "In the Motilal Oswal Midcap Fund SID load structure, what pair of 365-day exit rules is listed?",
        "table", True,
        [S(M, "1% - If redeemed on or before 365 days from the date of allotment. \nNil - If redeemed after 365 days from the date of allotment.")],
        ["1%", "Nil"])
    add("table_kotak_tier_rows", "In the Kotak Midcap Fund SID benchmark rows, what are Tier 1 and Tier 2?",
        "table", True,
        [S(K, "Tier 1: Nifty Midcap 150 TRI  Tier 2:Nifty Midcap 100 TRI")],
        ["150", "100"])
    add("table_hdfc_obj_row", "In the HDFC Mid Cap Fund SID particulars, what objective text follows Investment Objective?",
        "table", True,
        [S(H, "To provide long -term capital appreciation/income by investing \npredominantly in Mid-Cap companies.")],
        ["Mid-Cap companies"])
    add("table_sc_subject", "What subject line does the April 2024 SEBI circular carry?",
        "table", True,
        [S(SC, "Subject: Ease of doing business- Fund manager for Mutual fund schemes \ninvesting in commodities and overseas securities.")],
        ["Ease of doing business"])

    # paraphrase ≤30% overlap
    add("paraphrase_hdfc_former",
        "Under what earlier brand did the current HDFC mid-size equity scheme previously operate, per its SID?",
        "paraphrase", True,
        [S(H, "Formerly known as HDFC Mid-Cap Opportunities Fund")],
        ["HDFC Mid-Cap Opportunities Fund"])
    add("paraphrase_ppfas_horizon",
        "How long does PPFAS say an investor should plan to stay invested in its flexi-cap scheme?",
        "paraphrase", True,
        [S(P, "investment horizon of minimum 5 years")],
        ["5 years"])
    add("paraphrase_commodity_optional",
        "Does the April 2024 SEBI note require a specialist manager for gold and silver ETFs?",
        "paraphrase", True,
        [S(SC, "dedicated fund manager shall be optional")],
        ["optional"])
    add("paraphrase_master_supersede",
        "Which older consolidated mutual-fund rulebook does the June 2024 SEBI volume replace?",
        "paraphrase", True,
        [S(MC, "supersedes the Master Circular for Mutual Funds dated May 19, 2023")],
        ["May 19, 2023"])
    add("paraphrase_nippon_window",
        "After how short a holding period can Nippon Growth Mid Cap unit holders avoid the early redemption charge?",
        "paraphrase", True,
        [S(N, "1% if redeemed or switched out on or before completion of 1 month from the date of allotment of units. Nil, \nthereafter.")],
        ["1 month", "Nil"])
    add("paraphrase_kotak_legal",
        "What registered title sits in the Kotak mid-size equity SID particulars besides the cover branding?",
        "paraphrase", True,
        [S(K, "KOTAK EMERGING EQUITY FUND")],
        ["KOTAK EMERGING EQUITY FUND"])
    add("paraphrase_motilal_nil",
        "When does Motilal's midcap SID stop applying the early redemption fee?",
        "paraphrase", True,
        [S(M, "Nil - If redeemed after 365 days from the date of allotment.")],
        ["365 days"])
    add("paraphrase_hdfc_bench",
        "Which mid-size equity total-return gauge appears beside the HDFC scheme riskometer on the cover?",
        "paraphrase", True,
        [S(H, "NIFTY MIDCAP 150 (TRI)")],
        ["NIFTY MIDCAP 150"])

    # number_or_date extras
    add("number_master_date", "On what calendar date was SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90 issued?",
        "number_or_date", True,
        [S(MC, "SEBI/HO/IMD/IMD-PoD-1/P/CIR/2024/90 June 27, 2024")],
        ["June 27, 2024"])
    add("number_sc_date", "On what date was SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 issued?",
        "number_or_date", True,
        [S(SC, "SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 April 30, 2024")],
        ["April 30, 2024"])
    add("number_motilal_365", "How many days is the Motilal Oswal Midcap Fund paid exit-load window?",
        "number_or_date", True,
        [S(M, "1% - If redeemed on or before 365 days from the date of allotment.")],
        ["365"])
    add("number_ppfas_5y", "How many years is the minimum horizon noted on the Parag Parikh Flexi Cap Fund SID?",
        "number_or_date", True,
        [S(P, "investment horizon of minimum 5 years")],
        ["5"])

    # unanswerable
    ood = [
        ("ood_mars", "What is the capital of Mars colony Zeta-9?"),
        ("ood_nobel", "Who won the Nobel Prize in Literature in 2021 per these PDFs?"),
        ("ood_bitcoin", "What was Bitcoin's closing price on 1 January 2015?"),
        ("ood_cricket", "What was India's score in the 2011 World Cup final?"),
        ("ood_recipe", "How many cups of flour are in the chocolate cake recipe?"),
        ("ood_weather", "What was the rainfall in Mumbai on 12 July 2018?"),
        ("ood_movie", "Who directed Inception according to the indexed documents?"),
        ("ood_olympics", "How many gold medals did Japan win at Tokyo 2020?"),
        ("ood_apple_cfo", "Who is Apple's CFO according to these scheme documents?"),
        ("ood_tesla", "What was Tesla's Q3 2019 automotive revenue in USD?"),
    ]
    for qid, query in ood:
        add(qid, query, "unanswerable_out_of_domain", False, [], [], "absent from corpus")

    near = [
        ("near_hdfc_sharpe", "What is the Sharpe ratio of HDFC Mid Cap Fund in its SID?",
         "Risk metrics narrative may exist; Sharpe not a stated SID field here"),
        ("near_kotak_alpha", "What is the alpha of Kotak Midcap Fund versus Nifty Midcap 150?",
         "Benchmark named; alpha not provided"),
        ("near_motilal_ytm", "What is the portfolio YTM of Motilal Oswal Midcap Fund?",
         "Equity midcap SID; YTM not stated"),
        ("near_nippon_ter_in_master", "What TER does the SEBI Master Circular assign to Nippon India Growth Mid Cap Fund?",
         "Master circular does not set scheme TER values"),
        ("near_ppfas_midcap150", "Does the Parag Parikh Flexi Cap Fund SID use NIFTY Midcap 150 TRI as Tier I benchmark?",
         "PPFAS uses Nifty 500 TRI; Midcap 150 is other SIDs"),
        ("near_hdfc_code_in_kotak", "What HDFC scheme code is printed in the Kotak Midcap Fund SID?",
         "Wrong entity; Kotak has its own code"),
        ("near_aurora_ter", "What TER does Aurora Midcap Growth Fund list?",
         "Synthetic fund not in real corpus"),
        ("near_sc_supersede_may2023", "Does circular SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 supersede the May 2023 Master Circular?",
         "Supersession text is in the Master Circular PDF, not this short circular"),
        ("near_nippon_5year_horizon", "Does Nippon India Growth Mid Cap Fund require a minimum 5-year horizon like PPFAS?",
         "5-year note is PPFAS-specific"),
        ("near_hdfc_emerging_equity", "Is HDFC Mid Cap Fund's legal name KOTAK EMERGING EQUITY FUND?",
         "That legal name is Kotak's"),
        ("near_motilal_1month_exit", "Does Motilal Oswal Midcap Fund use a 1-month exit-load window like Nippon?",
         "Motilal uses 365 days; Nippon uses 1 month"),
        ("near_ppfas_scheme_code_hdfc", "Is PPFA/O/E/FCF/13/04/0001 the code for HDFC Mid Cap Fund?",
         "That code is PPFAS flexi cap"),
        ("near_master_april_30", "Was the Master Circular for Mutual Funds issued on April 30, 2024?",
         "April 30 is the short circular; Master is June 27, 2024"),
        ("near_kotak_nifty500", "Does Kotak Midcap Fund list Nifty 500 TRI as Tier 1 benchmark?",
         "Kotak lists Midcap 150/100; Nifty 500 is PPFAS"),
        ("near_third_violation_fine", "What fine applies on a third Master Circular violation instance?",
         "Field type may appear elsewhere; not asked entity-specific here"),
        ("near_sid_isin_hdfc", "What ISIN does the HDFC Mid Cap Fund SID print on page 1?",
         "ISIN often absent from cover; near-miss if not found in early pages"),
        ("near_overseas_ter", "What TER does the April 2024 circular prescribe for overseas funds?",
         "Circular addresses fund-manager appointment, not TER numbers"),
        ("near_bandhan_midcap_code", "What scheme code does Bandhan Midcap Fund use in this corpus?",
         "Bandhan SID not present; midcap codes exist for other AMCs"),
    ]
    for qid, query, note in near:
        add(qid, query, "unanswerable_near_miss", False, [], [], note)

    # Stratify 30/70 by category
    by_cat: dict[str, list[Question]] = {}
    for q in qs:
        by_cat.setdefault(q.category, []).append(q)
    rng = random.Random(11)
    for items in by_cat.values():
        rng.shuffle(items)
        n_tune = max(1, round(len(items) * 0.3)) if len(items) >= 3 else (1 if len(items) > 1 else 0)
        for i, q in enumerate(items):
            q.split = "tune" if i < n_tune else "test"

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
