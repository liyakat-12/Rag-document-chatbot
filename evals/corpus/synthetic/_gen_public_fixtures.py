"""Generate redistributable synthetic public PDFs for discriminative evaluation.

These are original fixtures (not scraped personal data). Near-identical fund schemes
share structure but differ in named fields so retrieval must disambiguate.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

CORPUS = Path(__file__).resolve().parent


def _pdf(path: Path, pages: list[list[str]]) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for lines in pages:
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        pdf.set_font("Helvetica", size=11)
        for line in lines:
            pdf.set_x(15)
            pdf.multi_cell(w=180, h=6, text=line)
    pdf.output(str(path))
    print(f"wrote {path.name} ({path.stat().st_size} bytes, {len(pages)} pages)")


def fund_scheme(
    name: str,
    code: str,
    isin: str,
    expense: str,
    aum: str,
    manager: str,
    risk: str,
    exit_load: str,
    *,
    doc_type: str,
    objective: str,
    benchmark: str,
    risk_blurb: str,
) -> list[list[str]]:
    return [
        [
            f"{name} - Scheme Information Document (SID)",
            f"Scheme code: {code}",
            f"ISIN: {isin}",
            f"Document type: {doc_type}",
            f"Investment objective: {objective}",
            f"Fund manager: {manager}",
            f"Riskometer: {risk}",
            f"Benchmark: {benchmark}",
            "This fixture is original text for DocuMind evaluation. Not a real offer document.",
        ],
        [
            f"{name} - Fees and expenses",
            f"Total Expense Ratio (TER): {expense}",
            f"Assets under management (AUM): {aum}",
            f"Exit load: {exit_load}",
            "Minimum subscription: INR 5,000.",
            "SIP minimum: INR 500 per month.",
            "Cut-off time for purchase: 3:00 PM IST.",
            "NAV publication: business days on the AMC website.",
            f"For scheme-specific TER always use the figure stated for {name} only.",
        ],
        [
            f"{name} - Risks and disclaimers",
            risk_blurb,
            f"Investors should read the SID of {name} carefully before investing.",
            "Past performance is not indicative of future results.",
            f"Contact: schemes@{code.split('-')[0].lower()}.example.invalid",
            "Distributor code field: blank in this fixture.",
            "Tax treatment depends on investor category and holding period.",
        ],
    ]


def main() -> None:
    # Shared family fields keep SIDs near-identical; TER/ISIN/AUM/code differ.
    aurora = dict(
        doc_type="Open-ended equity scheme - midcap (synthetic eval fixture).",
        objective="long-term capital appreciation focused on mid-capitalisation equities.",
        benchmark="NIFTY Midcap 150 TRI (illustrative).",
        risk_blurb="Equity investments are subject to market risk.",
    )
    boreal = dict(
        doc_type="Open-ended equity scheme - flexi cap (synthetic eval fixture).",
        objective="long-term capital appreciation across market caps.",
        benchmark="NIFTY 500 TRI (illustrative).",
        risk_blurb="Equity investments are subject to market risk.",
    )
    cascade = dict(
        doc_type="Open-ended debt scheme - low duration (synthetic eval fixture).",
        objective="income with capital preservation over a low-duration horizon.",
        benchmark="NIFTY Low Duration Debt Index A-I (illustrative).",
        risk_blurb="Debt investments carry interest-rate and credit risk.",
    )

    funds = [
        ("Aurora Midcap Growth Fund", "AMGF", "INF0AUD00001", "1.85%", "INR 12,400 crore",
         "Neha Kapoor", "Very High", "1% if redeemed within 365 days", aurora),
        ("Aurora Midcap Growth Fund - Direct", "AMGF-D", "INF0AUD00002", "0.95%", "INR 8,100 crore",
         "Neha Kapoor", "Very High", "1% if redeemed within 365 days", aurora),
        ("Boreal Flexi Cap Fund", "BFCF", "INF0BOR00011", "1.60%", "INR 21,750 crore",
         "Arjun Mehta", "High", "Nil", boreal),
        ("Boreal Flexi Cap Fund - Direct", "BFCF-D", "INF0BOR00012", "0.72%", "INR 14,200 crore",
         "Arjun Mehta", "High", "Nil", boreal),
        ("Cascade Low Duration Fund", "CLDF", "INF0CAS00021", "0.45%", "INR 3,050 crore",
         "Priya Nair", "Low to Moderate", "Nil", cascade),
        ("Cascade Low Duration Fund - Direct", "CLDF-D", "INF0CAS00022", "0.22%", "INR 1,880 crore",
         "Priya Nair", "Low to Moderate", "Nil", cascade),
    ]
    for name, code, isin, expense, aum, manager, risk, exit_load, extra in funds:
        fname = f"scheme_{code.replace('-', '_').lower()}.pdf"
        _pdf(
            CORPUS / fname,
            fund_scheme(
                name, code, isin, expense, aum, manager, risk, exit_load, **extra
            ),
        )

    _pdf(
        CORPUS / "circular_amc_disclosure_2024.pdf",
        [
            [
                "Regulatory Circular - AMC Portfolio Disclosure Timelines",
                "Circular ID: REG-AMC-DISC-2024-07",
                "Issued: 2024-07-18",
                "Applies to: all registered asset management companies in this fixture set.",
                "1. Monthly portfolio disclosure must be published within 10 days of month-end.",
                "2. Half-yearly financial results must be published within 60 days of period end.",
                "3. Scheme-wise TER changes above 5 basis points require investor notice.",
            ],
            [
                "Circular REG-AMC-DISC-2024-07 continued",
                "4. Soft-closure of schemes requires 15 business days public notice.",
                "5. Mis-selling complaints must be acknowledged within 3 business days.",
                "6. This circular does not set fund-specific TER values; those appear only in each SID.",
                "7. Contact for clarifications: circulars@regulator.example.invalid",
                "Annex A lists illustrative reporting templates (not included in this short fixture).",
            ],
            [
                "Circular REG-AMC-DISC-2024-07 - Enforcement",
                "Non-compliance may attract monetary penalties under the illustrative schedule:",
                "First instance: warning letter.",
                "Second instance within 12 months: INR 1,00,000 illustrative fine.",
                "The circular does not name Aurora, Boreal or Cascade TER figures.",
            ],
        ],
    )

    # Longer synthetic report to increase chunk count and dilute easy lexical hits
    report_pages: list[list[str]] = []
    report_pages.append(
        [
            "Comparative Note on Synthetic Midcap and Flexi Cap Schemes",
            "Report ID: CMP-NOTE-2024-11",
            "Author: DocuMind Eval Fixtures",
            "Purpose: Provide overlapping narrative so retrieval must use scheme-specific fields.",
            "The Aurora Midcap Growth Fund and Boreal Flexi Cap Fund both invest primarily in equities,",
            "but their TER, AUM and exit-load rules differ and must not be mixed.",
            "Cascade Low Duration Fund is not an equity scheme; treat it separately from the equity pair.",
        ]
    )
    topics = [
        ("Liquidity", "liquidity conditions and turnover vary by scheme and share class."),
        ("Risk labels", "riskometer labels are scheme-specific and must not be copied across SIDs."),
        ("Fees", "expense ratios differ between regular and Direct plans for the same brand."),
        ("Benchmarks", "benchmark indices differ; midcap references are not interchangeable with flexi-cap."),
        ("Debt vs equity", "Cascade Low Duration Fund is not an equity scheme."),
        ("Exit loads", "exit-load rules in Aurora Midcap Growth Fund differ from Boreal Flexi Cap Fund."),
        ("Disclosure", "investors should read each SID for TER and exit load rather than relying on this commentary."),
        ("AUM scale", "AUM figures are point-in-time fixtures and must be read from the named SID."),
        ("Managers", "fund managers are named per SID; do not assume shared management across brands."),
        ("Contact domains", "each SID publishes a distinct contact domain for scheme queries."),
        ("Regulatory scope", "circular REG-AMC-DISC-2024-07 sets process rules, not scheme TER numbers."),
        ("Near-miss fields", "Sharpe, alpha and YTM are not published in these synthetic SIDs."),
    ]
    for i, (title, body) in enumerate(topics, start=2):
        report_pages.append(
            [
                f"Section {i}: {title} (synthetic)",
                "Volatility in midcap segments can exceed large-cap indices over short windows.",
                "Investors comparing Aurora Midcap Growth Fund with Boreal Flexi Cap Fund should",
                "read each SID for TER and exit load rather than relying on this commentary.",
                f"Illustrative paragraph {i}.a: {body}",
                f"Illustrative paragraph {i}.b: repeating brand names without field values is intentional.",
                f"Illustrative paragraph {i}.c: this page intentionally avoids numeric TER values to force SID lookup.",
                "Padding sentence to enlarge chunk inventory without introducing answerable numeric facts.",
            ]
        )
    _pdf(CORPUS / "comparative_note_equity_schemes.pdf", report_pages)

    print("done")


if __name__ == "__main__":
    main()
