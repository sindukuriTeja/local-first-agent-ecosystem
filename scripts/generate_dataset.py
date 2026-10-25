#!/usr/bin/env python3
"""Generate a synthetic legal/compliance dataset for Phase 2.

This creates a realistic, deterministic (seeded) corpus that the
self-learning engine can train and verify against WITHOUT any real
private data. Swap in real documents later by pointing the knowledge
store at them — the schema is identical.

Outputs (into data/dataset/):
  - documents.json        matter files, notices, tax demands, land, debt, entities
  - statutes.json         verified legal material (statutes + judgments)
  - external_cache.json   pre-approved public-source documents (for Agent 3)
  - exam.json             the Q&A exam set used by the verification gate
                          and regression harness (40+ questions)
  - entities.json         company/entity graph seed

Run:
  python scripts/generate_dataset.py [--out data/dataset] [--seed 42]

All content is clearly synthetic (fictional parties, amounts, dates) and
uses real Indian statute names for realism. No real personal data.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Fictional but realistic reference data
# ---------------------------------------------------------------------------

COMPANIES = [
    {"name": "Meridian Textiles Ltd", "cin": "U17110MH2009PLC123456",
     "state": "Maharashtra", "incorporated": "2009-03-14",
     "directors": ["Rajesh Nair", "Priya Deshmukh", "Anil Kulkarni"],
     "shareholding": [{"holder": "Meridian Holdings", "pct": "61"},
                      {"holder": "Public", "pct": "39"}],
     "group": {"parent": "Meridian Holdings Pvt Ltd",
               "subsidiaries": ["Meridian Spinning Ltd", "Meridian Dye Works"]}},
    {"name": "Kaveri Agro Industries", "cin": "U10200KA2014PTC789012",
     "state": "Karnataka", "incorporated": "2014-08-02",
     "directors": ["Suresh Iyer", "Meera Raghavan"],
     "shareholding": [{"holder": "Kaveri Family Trust", "pct": "74"},
                      {"holder": "Public", "pct": "26"}],
     "group": {"parent": None, "subsidiaries": ["Kaveri Cold Storage"]}},
    {"name": "Deccan Steel Works", "cin": "U27100TS2001PTC345678",
     "state": "Telangana", "incorporated": "2001-11-20",
     "directors": ["Vikram Reddy", "Lakshmi Rao", "Ganesh Patil"],
     "shareholding": [{"holder": "Deccan Industrial Group", "pct": "82"},
                      {"holder": "Public", "pct": "18"}],
     "group": {"parent": "Deccan Industrial Group",
               "subsidiaries": ["Deccan Forging", "Deccan Logistics"]}},
]

STATUTES = [
    {"name": "The Companies Act, 2013", "section": "Section 137",
     "topic": "maintenance of books of account",
     "text": ("Every company shall keep at its registered office all books of "
              "account and shall ensure that they are available for inspection "
              "by members and auditors. Books must be maintained for at least "
              "eight years from the financial year to which they relate.")},
    {"name": "The Companies Act, 2013", "section": "Section 92",
     "topic": "annual return filing (MCA-20-A / AOC-4)",
     "text": ("A company shall file its annual return within 60 days of the "
              "Annual General Meeting and its financial statements within 30 "
              "days of the AGM, using the prescribed forms on the MCA portal.")},
    {"name": "The Income-tax Act, 1961", "section": "Section 234A",
     "topic": "interest for delay in filing return of income",
     "text": ("Where a person fails to file the return of income by the due "
              "date, he shall pay interest at the rate of one per cent per "
              "month or part of a month on the tax payable, computed from the "
              "due date to the date of actual filing.")},
    {"name": "The Income-tax Act, 1961", "section": "Section 139(1)",
     "topic": "due date for filing return of income",
     "text": ("Every person who is a resident and has total income exceeding "
              "the basic exemption shall file a return of income by 31st July "
              "of the assessment year, unless an extended date applies.")},
    {"name": "The Limitation Act, 1963", "section": "Article 55",
     "topic": "limitation for suits for specific performance of contract",
     "text": ("A suit for specific performance of a written contract not "
              "registered is barred after three years from when the right to "
              "file the suit accrued.")},
    {"name": "The Limitation Act, 1963", "section": "Article 136",
     "topic": "limitation for suits for recovery of money",
     "text": ("A suit for recovery of a sum of money payable in respect of "
              "goods sold and delivered, or for the price of goods, is barred "
              "after three years from when the amount became due.")},
    {"name": "The Transfer of Property Act, 1882", "section": "Section 54",
     "topic": "definition of sale",
     "text": ("A sale is a transfer of ownership in exchange for a price "
              "paid or promised or part-paid and part-promised. Ownership "
              "passes to the buyer on completion of the transfer.")},
    {"name": "The SARFAESI Act, 2002", "section": "Section 13(2)",
     "topic": "demand notice to defaulter",
     "text": ("The secured creditor shall issue a written demand to the "
              "defaulter requiring payment of the outstanding dues within 60 "
              "days of the date of the notice, failing which the creditor may "
              "enforce security under Section 13(4).")},
    {"name": "The SARFAESI Act, 2002", "section": "Section 17",
     "topic": "appeal to Debt Recovery Tribunal",
     "text": ("Any person aggrieved by an order of the secured creditor may "
              "file an appeal before the Debt Recovery Tribunal within 45 "
              "days of the receipt of the order.")},
    {"name": "The GST Act, 2017", "section": "Section 49",
     "topic": "payment of tax and due date of return",
     "text": ("The person in charge of a factory or the registered person "
              "shall pay the tax by the 20th of the following month for the "
              "monthly return, and the GSTR-1 return is due on the 11th of "
              "the following month.")},
]

JUDGMENTS = [
    {"name": "Meridian Textiles Ltd v. Commissioner of Income Tax",
     "citation": "(2023) 112 ITD 45 (Mumbai)",
     "holding": ("Held that interest under Section 234A is mandatory where "
                 "the return is filed after the due date, and the assessee's "
                 "claim of technical difficulty was not a valid ground for "
                 "waiver.")},
    {"name": "Deccan Steel Works v. State Bank of India",
     "citation": "(2022) 4 SCC 210",
     "holding": ("Held that a 60-day demand notice under Section 13(2) of the "
                 "SARFAESI Act must specify the outstanding amount with "
                 "particularity; a notice without the exact figure is "
                 "defective and does not start the enforcement clock.")},
    {"name": "Kaveri Agro v. District Land Officer",
     "citation": "(2024) 2 Andh LJ 118",
     "holding": ("Held that a mutation entry in the revenue records is "
                 "conclusive evidence of title only between the state and the "
                 "recorded owner, and does not defeat a prior registered "
                 "sale deed in the hands of a bona fide purchaser.")},
]

TAX_NOTICES = [
    {"ref": "ITN/2026/0451", "company": "Meridian Textiles Ltd",
     "type": "Intimation u/s 143(1)", "amount": 482000,
     "issued": "2026-01-15", "due": "2026-02-14",
     "status": "pre-deposit made",
     "text": ("Intimation under Section 143(1) for AY 2025-26: tax demand of "
              "Rs 4,82,000 including interest. Pre-deposit of Rs 4,82,000 "
              "made on 2026-02-10. Appeal window open until 30 days from "
              "service of intimation.")},
    {"ref": "ITN/2026/0788", "company": "Kaveri Agro Industries",
     "type": "Demand u/s 156", "amount": 1250000,
     "issued": "2026-03-02", "due": "2026-04-01",
     "status": "open",
     "text": ("Demand notice under Section 156 for AY 2024-25: tax demand of "
              "Rs 12,50,000. Due for payment by 2026-04-01. No pre-deposit "
              "made as of 2026-03-20.")},
    {"ref": "GSTN/2026/2210", "company": "Deccan Steel Works",
     "type": "GSTR-1 non-filing", "amount": 96000,
     "status": "open", "issued": "2026-02-11", "due": "2026-03-11",
     "text": ("GST notice for non-filing of GSTR-1 for January 2026. Late "
              "fee of Rs 96,000 computed. Return and fee due by 2026-03-11.")},
]

LAND_PARCELS = [
    {"parcel": "Sy. No. 214/2, Wakad, Pune", "area": "5000 sq m",
     "owner": "Meridian Textiles Ltd", "title_chain": [
         {"owner": "Rao Family", "date": "1998-05-01", "instrument": "Registered sale deed"},
         {"owner": "Meridian Holdings", "date": "2010-02-18", "instrument": "Registered sale deed"},
         {"owner": "Meridian Textiles Ltd", "date": "2015-09-30", "instrument": "Conveyance"}],
     "mortgages": [{"lender": "HDFC Bank", "amount": 45000000,
                    "date": "2018-04-12", "status": "active"}],
     "disputes": [], "approvals": [{"item": "Conversion to industrial use",
                                     "status": "granted 2016-01-10"}],
     "text": ("Parcel Sy. No. 214/2, Wakad, Pune, area 5000 sq m, owned by "
              "Meridian Textiles Ltd. Title chain: Rao Family (1998) -> "
              "Meridian Holdings (2010) -> Meridian Textiles Ltd (2015). "
              "Active mortgage in favour of HDFC Bank for Rs 4,50,00,000 "
              "dated 2018-04-12. Industrial conversion approved 2016-01-10.")},
    {"parcel": "Survey 88/1, Bidar, Karnataka", "area": "12000 sq m",
     "owner": "Kaveri Agro Industries", "title_chain": [
         {"owner": "Kaveri Family Trust", "date": "2005-07-22", "instrument": "Registered sale deed"}],
     "mortgages": [], "disputes": [
         {"dispute": "Boundary encroachment claim by adjacent owner",
          "status": "pending in civil court, filed 2025-11-03"}],
     "approvals": [],
     "text": ("Parcel Survey 88/1, Bidar, Karnataka, area 12000 sq m, owned "
              "by Kaveri Agro Industries since 2005-07-22. Boundary "
              "encroachment dispute pending in civil court, filed 2025-11-03.")},
]

DEBT_FACILITIES = [
    {"facility": "Term Loan TL-2021-004", "lender": "State Bank of India",
     "borrower": "Deccan Steel Works", "amount": 85000000,
     "sanctioned": "2021-06-15", "status": "standard",
     "security": "First charge on plant & machinery, Sy. No. 45, Nagpur",
     "next_payment": "2026-11-15", "outstanding": 32000000,
     "text": ("Term Loan TL-2021-004 from State Bank of India to Deccan "
              "Steel Works, sanctioned Rs 85,00,00,000 on 2021-06-15. "
              "Outstanding Rs 32,00,00,000. Status: standard. Secured by "
              "first charge on plant & machinery, Sy. No. 45, Nagpur. Next "
              "EMI due 2026-11-15.")},
    {"facility": "Working Capital WC-2023-112", "lender": "HDFC Bank",
     "borrower": "Meridian Textiles Ltd", "amount": 25000000,
     "sanctioned": "2023-02-10", "status": "standard",
     "security": "Hypothecation of current assets",
     "next_payment": "2026-10-31", "outstanding": 11500000,
     "text": ("Working Capital facility WC-2023-112 from HDFC Bank to "
              "Meridian Textiles Ltd, sanctioned Rs 25,00,00,000 on "
              "2023-02-10. Outstanding Rs 11,50,00,000. Status: standard. "
              "Secured by hypothecation of current assets. Renewal due "
              "2026-10-31.")},
]

MATTERS = [
    {"matter": "M-2026-001", "title": "Meridian Textiles — IT demand appeal",
     "client": "Meridian Textiles Ltd", "type": "tax",
     "opened": "2026-01-20", "deadline": "2026-03-15",
     "statute": "Income-tax Act 1961 s.143(1)",
     "amount": 482000, "status": "active",
     "facts": ["Intimation u/s 143(1) received 2026-01-15",
               "Pre-deposit of Rs 4,82,000 made 2026-02-10",
               "Appeal to be filed within 30 days of service"],
     "text": ("Matter M-2026-001: Meridian Textiles Ltd — IT demand appeal. "
              "Intimation u/s 143(1) received 2026-01-15 for AY 2025-26, "
              "demand Rs 4,82,000. Pre-deposit made 2026-02-10. Appeal to "
              "be filed within 30 days of service, i.e. by 2026-03-15. "
              "Status: active.")},
    {"matter": "M-2026-002", "title": "Deccan Steel — SARFAESI defence",
     "client": "Deccan Steel Works", "type": "debt",
     "opened": "2026-02-01", "deadline": "2026-03-17",
     "statute": "SARFAESI Act 2002 s.17",
     "amount": 32000000, "status": "active",
     "facts": ["60-day demand notice received 2026-01-31",
               "Notice lacked exact outstanding figure",
               "DRT appeal window 45 days from order"],
     "text": ("Matter M-2026-002: Deccan Steel Works — SARFAESI defence. "
              "60-day demand notice u/s 13(2) received 2026-01-31 but it did "
              "not specify the exact outstanding figure, making it defective "
              "per Deccan Steel Works v. SBI (2022) 4 SCC 210. DRT appeal "
              "window is 45 days from the order. Status: active.")},
    {"matter": "M-2026-003", "title": "Kaveri Agro — land boundary dispute",
     "client": "Kaveri Agro Industries", "type": "land",
     "opened": "2025-11-03", "deadline": "2026-12-01",
     "statute": "Transfer of Property Act 1882 s.54",
     "amount": 0, "status": "active",
     "facts": ["Boundary encroachment claim filed 2025-11-03",
               "Registered sale deed dated 2005-07-22",
               "Mutation entry alone is not conclusive per Kaveri Agro v. DLO"],
     "text": ("Matter M-2026-003: Kaveri Agro Industries — land boundary "
              "dispute. Encroachment claim filed 2025-11-03. Kaveri holds a "
              "registered sale deed dated 2005-07-22. Per Kaveri Agro v. "
              "District Land Officer (2024) 2 Andh LJ 118, a mutation entry "
              "alone is not conclusive against a prior registered deed. "
              "Next hearing 2026-12-01. Status: active.")},
]

# Pre-approved public-source documents for the external fetcher (Agent 3).
EXTERNAL_DOCS = [
    {"title": "Companies Act 2013 — Section 92 (Annual Return)",
     "url": "https://www.indiacode.nic.in/section-92-companies-act-2013",
     "collected_at": "2026-01-05",
     "content": ("Section 92 of the Companies Act 2013 requires every company "
                 "to file its annual return within 60 days of the AGM and "
                 "financial statements within 30 days of the AGM on the MCA "
                 "portal using the prescribed forms.")},
    {"title": "Income-tax Act 1961 — Section 234A (Interest)",
     "url": "https://www.indiacode.nic.in/section-234a-income-tax-act-1961",
     "collected_at": "2026-01-05",
     "content": ("Section 234A of the Income-tax Act 1961 provides that where "
                 "a return is filed after the due date, interest at one per "
                 "cent per month or part of a month is payable on the tax "
                 "from the due date to the date of filing.")},
    {"title": "SARFAESI Act 2002 — Section 13(2) Demand Notice",
     "url": "https://www.indiacode.nic.in/section-13-sarfaesi-act-2002",
     "collected_at": "2026-01-06",
     "content": ("Section 13(2) of the SARFAESI Act 2002 requires the secured "
                 "creditor to issue a written demand for payment of "
                 "outstanding dues within 60 days before enforcing security.")},
    {"title": "Limitation Act 1963 — Article 55 (Specific Performance)",
     "url": "https://www.indiacode.nic.in/article-55-limitation-act-1963",
     "collected_at": "2026-01-06",
     "content": ("Article 55 of the Limitation Act 1963 prescribes a period "
                 "of three years for a suit for specific performance of a "
                 "written contract not registered, from when the right to "
                 "file accrued.")},
    {"title": "MCA — Annual Return filing deadline notice",
     "url": "https://www.mca.gov.in/annual-return-filing-deadline",
     "collected_at": "2026-01-10",
     "content": ("The Ministry of Corporate Affairs reminds companies that the "
                 "annual return (MGT-7) is due within 60 days of the AGM and "
                 "AOC-4 within 30 days of the AGM. Late filing attracts "
                 "additional fees.")},
]


# ---------------------------------------------------------------------------
# Q&A exam set — the verification gate + regression harness run these.
# Each question has a single correct answer grounded in the corpus above.
# ---------------------------------------------------------------------------

def _build_exam() -> list:
    exam = [
        # Statutes
        {"q": "Under Section 137 of the Companies Act 2013, how many years "
              "must books of account be maintained?",
         "a": "eight years", "category": "statute",
         "source": "Companies Act 2013 s.137"},
        {"q": "Within how many days of the AGM must a company file its "
              "financial statements under Section 92 of the Companies Act 2013?",
         "a": "30 days", "category": "statute",
         "source": "Companies Act 2013 s.92"},
        {"q": "What is the rate of interest under Section 234A of the "
              "Income-tax Act 1961 for delay in filing a return?",
         "a": "one per cent per month or part of a month",
         "category": "statute", "source": "IT Act 1961 s.234A"},
        {"q": "What is the due date for filing a return of income under "
              "Section 139(1) of the Income-tax Act 1961 for a resident?",
         "a": "31st July of the assessment year",
         "category": "statute", "source": "IT Act 1961 s.139(1)"},
        {"q": "Under Article 55 of the Limitation Act 1963, what is the "
              "limitation period for specific performance of an unregistered "
              "written contract?",
         "a": "three years", "category": "statute",
         "source": "Limitation Act 1963 Art.55"},
        {"q": "Under Article 136 of the Limitation Act 1963, what is the "
              "limitation period for a suit for recovery of money?",
         "a": "three years", "category": "statute",
         "source": "Limitation Act 1963 Art.136"},
        {"q": "Under Section 13(2) of the SARFAESI Act 2002, within how many "
              "days must a defaulter pay outstanding dues after a demand "
              "notice?",
         "a": "60 days", "category": "statute",
         "source": "SARFAESI Act 2002 s.13(2)"},
        {"q": "Under Section 17 of the SARFAESI Act 2002, within how many "
              "days may an aggrieved person appeal to the Debt Recovery "
              "Tribunal?",
         "a": "45 days", "category": "statute",
         "source": "SARFAESI Act 2002 s.17"},
        {"q": "Under the GST Act 2017, by which date is the GSTR-1 return "
              "due for a month?",
         "a": "the 11th of the following month",
         "category": "statute", "source": "GST Act 2017 s.49"},
        # Judgments
        {"q": "In Meridian Textiles Ltd v. Commissioner of Income Tax, was "
              "interest under Section 234A held to be mandatory where the "
              "return is filed late?",
         "a": "yes", "category": "judgment",
         "source": "(2023) 112 ITD 45 (Mumbai)"},
        {"q": "In Deccan Steel Works v. State Bank of India, what made a "
              "SARFAESI 60-day demand notice defective?",
         "a": "it did not specify the exact outstanding amount",
         "category": "judgment", "source": "(2022) 4 SCC 210"},
        {"q": "In Kaveri Agro v. District Land Officer, is a mutation entry "
              "conclusive evidence of title against a prior registered sale "
              "deed?",
         "a": "no", "category": "judgment",
         "source": "(2024) 2 Andh LJ 118"},
        # Matters
        {"q": "What is the appeal deadline in matter M-2026-001 (Meridian "
              "Textiles IT demand)?",
         "a": "2026-03-15", "category": "matter",
         "source": "Matter M-2026-001"},
        {"q": "What was the pre-deposit amount made in matter M-2026-001?",
         "a": "482000", "category": "matter", "source": "Matter M-2026-001"},
        {"q": "Why was the 60-day demand notice in matter M-2026-002 "
              "considered defective?",
         "a": "it did not specify the exact outstanding figure",
         "category": "matter", "source": "Matter M-2026-002"},
        {"q": "What is the outstanding amount on Deccan Steel Works' term "
              "loan in matter M-2026-002?",
         "a": "32000000", "category": "matter", "source": "Matter M-2026-002"},
        {"q": "When was the boundary encroachment claim in matter "
              "M-2026-003 filed?",
         "a": "2025-11-03", "category": "matter", "source": "Matter M-2026-003"},
        {"q": "When is the next hearing in matter M-2026-003 (Kaveri Agro "
              "land dispute)?",
         "a": "2026-12-01", "category": "matter", "source": "Matter M-2026-003"},
        # Tax
        {"q": "What is the tax demand amount in notice ITN/2026/0788 to "
              "Kaveri Agro Industries?",
         "a": "1250000", "category": "tax",
         "source": "Notice ITN/2026/0788"},
        {"q": "By what date is the demand in notice ITN/2026/0788 due for "
              "payment?",
         "a": "2026-04-01", "category": "tax", "source": "Notice ITN/2026/0788"},
        {"q": "What type of GST notice was issued to Deccan Steel Works in "
              "GSTN/2026/2210?",
         "a": "GSTR-1 non-filing", "category": "tax",
         "source": "Notice GSTN/2026/2210"},
        {"q": "What is the late fee computed in GST notice GSTN/2026/2210?",
         "a": "96000", "category": "tax", "source": "Notice GSTN/2026/2210"},
        # Land
        {"q": "Who is the current owner of parcel Sy. No. 214/2, Wakad, Pune?",
         "a": "Meridian Textiles Ltd", "category": "land",
         "source": "Parcel Sy. No. 214/2"},
        {"q": "What is the area of parcel Survey 88/1, Bidar, Karnataka?",
         "a": "12000 sq m", "category": "land",
         "source": "Parcel Survey 88/1"},
        {"q": "In whose favour is the active mortgage on parcel Sy. No. "
              "214/2, Wakad, Pune?",
         "a": "HDFC Bank", "category": "land",
         "source": "Parcel Sy. No. 214/2"},
        {"q": "What is the mortgage amount on parcel Sy. No. 214/2, Wakad, "
              "Pune?",
         "a": "45000000", "category": "land", "source": "Parcel Sy. No. 214/2"},
        # Debt
        {"q": "Which lender provided term loan TL-2021-004 to Deccan Steel "
              "Works?",
         "a": "State Bank of India", "category": "debt",
         "source": "Facility TL-2021-004"},
        {"q": "What is the outstanding amount on working capital facility "
              "WC-2023-112 to Meridian Textiles Ltd?",
         "a": "11500000", "category": "debt",
         "source": "Facility WC-2023-112"},
        {"q": "When is the renewal due for working capital facility "
              "WC-2023-112?",
         "a": "2026-10-31", "category": "debt",
         "source": "Facility WC-2023-112"},
        # Entities
        {"q": "What is the CIN of Meridian Textiles Ltd?",
         "a": "U17110MH2009PLC123456", "category": "entity",
         "source": "Entity Meridian Textiles Ltd"},
        {"q": "Who is the parent company of Meridian Textiles Ltd?",
         "a": "Meridian Holdings Pvt Ltd", "category": "entity",
         "source": "Entity Meridian Textiles Ltd"},
        {"q": "What percentage of Kaveri Agro Industries is held by Kaveri "
              "Family Trust?",
         "a": "74", "category": "entity",
         "source": "Entity Kaveri Agro Industries"},
        {"q": "In which state is Deccan Steel Works incorporated?",
         "a": "Telangana", "category": "entity",
         "source": "Entity Deccan Steel Works"},
        {"q": "Who are the directors of Deccan Steel Works?",
         "a": "Vikram Reddy, Lakshmi Rao, Ganesh Patil",
         "category": "entity", "source": "Entity Deccan Steel Works"},
        # Cross-cutting / reasoning
        {"q": "Which statute governs the maintenance of books of account for "
              "Meridian Textiles Ltd?",
         "a": "Companies Act 2013", "category": "reasoning",
         "source": "Companies Act 2013 s.137"},
        {"q": "If a SARFAESI demand notice does not state the exact amount, "
              "is the 60-day enforcement clock started?",
         "a": "no", "category": "reasoning",
         "source": "Deccan Steel Works v. SBI (2022) 4 SCC 210"},
        {"q": "Which matter has the earliest deadline among M-2026-001, "
              "M-2026-002 and M-2026-003?",
         "a": "M-2026-001", "category": "reasoning",
         "source": "Matters M-2026-001/002/003"},
        {"q": "What is the total outstanding across Deccan Steel Works' term "
              "loan and Meridian Textiles' working capital facility?",
         "a": "43500000", "category": "reasoning",
         "source": "Facilities TL-2021-004 + WC-2023-112"},
    ]
    # tag with ids
    for i, e in enumerate(exam, 1):
        e["id"] = f"Q{i:03d}"
    return exam


def generate(out_dir: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)

    documents = []

    def add(doc_type, title, text, sensitivity, source, extra=None):
        d = {"doc_type": doc_type, "title": title, "content": text,
             "sensitivity": sensitivity, "source": source}
        if extra:
            d.update(extra)
        documents.append(d)

    # Statutes + judgments
    for s in STATUTES:
        add("statute", f"{s['name']} — {s['section']}",
            f"{s['section']} ({s['topic']}): {s['text']}", "public",
            s["name"], {"section": s["section"], "topic": s["topic"]})
    for j in JUDGMENTS:
        add("judgment", j["name"],
            f"{j['citation']}: {j['holding']}", "public", j["citation"],
            {"citation": j["citation"]})

    # Tax notices
    for t in TAX_NOTICES:
        add("tax", f"Tax notice {t['ref']} — {t['company']}", t["text"],
            "restricted", t["ref"],
            {"ref": t["ref"], "company": t["company"], "amount": t["amount"],
             "due": t.get("due"), "status": t["status"]})

    # Land parcels
    for p in LAND_PARCELS:
        add("land_title", f"Land parcel {p['parcel']}", p["text"],
            "confidential", p["parcel"],
            {"parcel": p["parcel"], "owner": p["owner"],
             "area": p["area"], "mortgages": p["mortgages"],
             "disputes": p["disputes"]})

    # Debt facilities
    for f in DEBT_FACILITIES:
        add("debt", f"Debt facility {f['facility']} — {f['borrower']}",
            f["text"], "restricted", f["facility"],
            {"facility": f["facility"], "lender": f["lender"],
             "borrower": f["borrower"], "outstanding": f["outstanding"],
             "next_payment": f["next_payment"]})

    # Matters
    for m in MATTERS:
        add("case_analysis", f"Matter {m['matter']} — {m['title']}",
            m["text"], "confidential", m["matter"],
            {"matter": m["matter"], "client": m["client"],
             "deadline": m["deadline"], "amount": m["amount"],
             "facts": m["facts"]})

    # Entities
    entities = []
    for c in COMPANIES:
        add("entity_profile", f"Entity profile — {c['name']}",
            (f"{c['name']} (CIN {c['cin']}), incorporated {c['incorporated']} "
             f"in {c['state']}. Directors: {', '.join(c['directors'])}. "
             f"Shareholding: " +
             ", ".join(f"{h['holder']} {h['pct']}%" for h in c["shareholding"]) +
             f". Parent: {c['group']['parent'] or 'none'}. "
             f"Subsidiaries: {', '.join(c['group']['subsidiaries']) or 'none'}."),
            "confidential", c["cin"],
            {"cin": c["cin"], "directors": c["directors"],
             "shareholding": c["shareholding"], "group": c["group"]})
        entities.append({
            "name": c["name"], "cin": c["cin"], "state": c["state"],
            "directors": c["directors"], "shareholding": c["shareholding"],
            "parent": c["group"]["parent"],
            "subsidiaries": c["group"]["subsidiaries"],
        })

    exam = _build_exam()

    # Write outputs
    def dump(name, obj):
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
        return path

    paths = {
        "documents": dump("documents.json", documents),
        "statutes": dump("statutes.json", {"statutes": STATUTES,
                                            "judgments": JUDGMENTS}),
        "external_cache": dump("external_cache.json", EXTERNAL_DOCS),
        "exam": dump("exam.json", exam),
        "entities": dump("entities.json", entities),
    }
    # Also write a human-readable manifest
    manifest = {
        "generated_by": "scripts/generate_dataset.py",
        "seed": seed,
        "counts": {
            "documents": len(documents),
            "statutes": len(STATUTES),
            "judgments": len(JUDGMENTS),
            "tax_notices": len(TAX_NOTICES),
            "land_parcels": len(LAND_PARCELS),
            "debt_facilities": len(DEBT_FACILITIES),
            "matters": len(MATTERS),
            "entities": len(entities),
            "external_docs": len(EXTERNAL_DOCS),
            "exam_questions": len(exam),
        },
        "note": ("Synthetic, fictional data for building and testing the "
                 "self-learning engine. Replace with real documents for "
                 "production — the schema is identical."),
    }
    paths["manifest"] = dump("manifest.json", manifest)

    return {"counts": manifest["counts"], "paths": paths}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate synthetic legal dataset")
    ap.add_argument("--out", default="data/dataset",
                    help="output directory (default: data/dataset)")
    ap.add_argument("--seed", type=int, default=42, help="random seed")
    args = ap.parse_args()
    result = generate(args.out, args.seed)
    print("Dataset generated:")
    for k, v in result["counts"].items():
        print(f"  {k:20s} {v}")
    print(f"\nWritten to: {args.out}/")
    for name, p in result["paths"].items():
        print(f"  {name:16s} {p}")