import json, glob

# Multiple valid XBRL tags can represent the same underlying financial concept.
# This is a real taxonomy quirk, not a data quality problem — document it as such.
TAG_CANDIDATES = {
    "NetIncomeLoss": ["NetIncomeLoss", "ProfitLoss"],
    "Revenues": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "InterestAndDividendIncomeOperating",  # common for banks/financials in place of "Revenues"
    ],
    "Assets": ["Assets"],
}

for path in sorted(glob.glob("data/raw/xbrl/*_xbrl.json")):
    with open(path) as f:
        data = json.load(f)
    ticker = path.split("/")[-1].replace("_xbrl.json", "")
    us_gaap = data.get("facts", {}).get("us-gaap", {})

    result = {}
    for concept, candidates in TAG_CANDIDATES.items():
        found_tag = next((c for c in candidates if c in us_gaap), None)
        result[concept] = found_tag

    missing = [k for k, v in result.items() if v is None]
    if missing:
        print(f"{ticker}: STILL MISSING {missing} — check this filer manually")
    else:
        tag_summary = ", ".join(f"{k}->{v}" for k, v in result.items())
        print(f"{ticker}: OK ({tag_summary})")