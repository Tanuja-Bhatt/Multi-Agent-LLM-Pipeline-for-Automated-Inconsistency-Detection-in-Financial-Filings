import requests
import json
import csv
import time
from pathlib import Path
from datetime import datetime, date

# Configuration
BASE_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{}.json"
BASE_SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{}"  # for paginated older-filings files
BASE_XBRL_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{}.json"
BASE_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}"

HEADERS = {
    "User-Agent": "GraphicEraHillUniversity FinancialFilingsProject (student@gehu.ac.in)"
}

FY_WINDOW_START = date(2022, 1, 1)
FY_WINDOW_CUTOFF = date(2023, 2, 28)  # latest acceptable reportDate — excludes non-Dec FYE companies'
                                        # NEXT fiscal year (e.g. MSFT/PG FY ending 2023-06-30, MDT ending 2023-04-28)
                                        # while still including Jan-ending retailers' "FY2022" (WMT, TGT)
DELAY_BETWEEN_REQUESTS = 0.2

Path("data/raw/filings").mkdir(parents=True, exist_ok=True)
Path("data/raw/xbrl").mkdir(parents=True, exist_ok=True)
Path("data/metadata").mkdir(parents=True, exist_ok=True)


def pad_cik(cik):
    """SEC's data.sec.gov endpoints require a 10-digit, zero-padded CIK."""
    return str(int(cik)).zfill(10)


def fetch_json(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    time.sleep(DELAY_BETWEEN_REQUESTS)
    return response.json()


def fetch_html(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    time.sleep(DELAY_BETWEEN_REQUESTS)
    return response.text


def candidates_from_filings_block(filings_block):
    """Yield (form, filingDate, reportDate, accessionNumber, primaryDocument) for 10-Ks in a filings block."""
    forms = filings_block.get('form', [])
    for i, form in enumerate(forms):
        if form == '10-K':
            yield {
                "filingDate": filings_block['filingDate'][i],
                "reportDate": filings_block['reportDate'][i],
                "accessionNumber": filings_block['accessionNumber'][i],
                "primaryDocument": filings_block['primaryDocument'][i],
            }


def get_10k_filing(cik, ticker):
    """
    Find the 10-K whose reportDate is closest to TARGET_FY_END, within FY_WINDOW_DAYS.
    Checks filings['recent'] first, then falls back to paginated older-filings files
    (needed for high-volume filers like banks, whose 10-K can fall out of 'recent').
    Returns dict with accessionNumber/primaryDocument/reportDate, or None.
    """
    cik_padded = pad_cik(cik)
    submissions_url = BASE_SUBMISSIONS_URL.format(cik_padded)
    print(f"  Fetching submission history for {ticker} (CIK {cik_padded})...")

    try:
        data = fetch_json(submissions_url)
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP ERROR {e.response.status_code} fetching submissions for {ticker} "
              f"(CIK {cik_padded}) — check that this CIK is correct.")
        return None

    all_candidates = list(candidates_from_filings_block(data['filings']['recent']))

    # Fallback: paginated historical filings (high-volume filers, e.g. banks)
    for file_ref in data['filings'].get('files', []):
        page_url = BASE_SUBMISSIONS_PAGE_URL.format(file_ref['name'])
        try:
            page_data = fetch_json(page_url)
            all_candidates.extend(candidates_from_filings_block(page_data))
        except requests.exceptions.HTTPError as e:
            print(f"  WARNING: could not fetch paginated filings page {file_ref['name']} "
                  f"for {ticker}: HTTP {e.response.status_code}")

    if not all_candidates:
        print(f"  WARNING: no 10-K filings found at all for {ticker}")
        return None

    
    # Pick the LATEST reportDate that still falls within the acceptable window.
    # "Closest to a fixed calendar date" is wrong for non-Dec fiscal-year-end companies —
    # it can pick the NEXT fiscal year if that happens to land numerically closer.
    best = None
    for c in all_candidates:
        try:
            report_date = datetime.strptime(c['reportDate'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if FY_WINDOW_START <= report_date <= FY_WINDOW_CUTOFF:
            if best is None or report_date > datetime.strptime(best['reportDate'], "%Y-%m-%d").date():
                best = c

    if best is None:
        nearest = min(all_candidates, key=lambda c: c['reportDate'])
        print(f"  WARNING: no 10-K in window [{FY_WINDOW_START}, {FY_WINDOW_CUTOFF}] for {ticker}. "
              f"Nearest available reportDate: {nearest['reportDate']} — inspect manually.")
        return None

    print(f"  Found 10-K: reportDate={best['reportDate']}, filed={best['filingDate']}")
    return best


def download_filing(cik, ticker, accession, primary_doc):
    accession_no_dash = accession.replace('-', '')
    cik_clean = str(int(cik))  # Archives URLs want CIK WITHOUT leading zeros — this part was already correct
    filing_url = BASE_FILING_URL.format(cik_clean, accession_no_dash, primary_doc)
    print(f"  Downloading filing from {filing_url}")
    html_content = fetch_html(filing_url)
    output_path = f"data/raw/filings/{ticker}_2022.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"  Saved to {output_path}")
    return output_path


def download_xbrl(cik, ticker):
    cik_padded = pad_cik(cik)
    xbrl_url = BASE_XBRL_URL.format(cik_padded)
    print(f"  Downloading XBRL facts from {xbrl_url}")
    try:
        xbrl_data = fetch_json(xbrl_url)
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP ERROR {e.response.status_code} fetching XBRL for {ticker} — "
              f"some filers (esp. smaller/foreign private issuers) may lack companyfacts data.")
        raise
    output_path = f"data/raw/xbrl/{ticker}_xbrl.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(xbrl_data, f, indent=2)
    print(f"  Saved to {output_path}")
    return output_path


def main():
    with open('data/companies.csv', 'r') as f:
        companies = list(csv.DictReader(f))

    corpus_index = []
    failures = []

    print(f"Starting EDGAR data collection for {len(companies)} companies...\n")

    for company in companies:
        ticker = company['ticker']
        cik = company['cik']
        name = company['name']

        print(f"\n[{ticker}] {name} (CIK: {cik})")
        print("=" * 60)

        try:
            filing_info = get_10k_filing(cik, ticker)
            if not filing_info:
                failures.append({"ticker": ticker, "reason": "no matching 10-K found"})
                continue

            filing_path = download_filing(cik, ticker, filing_info['accessionNumber'], filing_info['primaryDocument'])
            xbrl_path = download_xbrl(cik, ticker)

            corpus_index.append({
                "ticker": ticker,
                "company_name": name,
                "cik": pad_cik(cik),
                "filing_date": filing_info['filingDate'],
                "report_date": filing_info['reportDate'],
                "accession_number": filing_info['accessionNumber'],
                "filing_path": filing_path,
                "xbrl_path": xbrl_path,
                "downloaded_at": datetime.now().isoformat()
            })
            print(f"  \u2713 Successfully fetched {ticker}")

        except requests.exceptions.HTTPError as e:
            print(f"  ERROR fetching {ticker}: HTTP {e.response.status_code} on {e.response.url}")
            failures.append({"ticker": ticker, "reason": f"HTTP {e.response.status_code}"})
            continue
        except Exception as e:
            print(f"  ERROR fetching {ticker}: {type(e).__name__}: {e}")
            failures.append({"ticker": ticker, "reason": str(e)})
            continue

    with open('data/metadata/corpus_index.json', 'w') as f:
        json.dump(corpus_index, f, indent=2)

    with open('data/metadata/fetch_failures.json', 'w') as f:
        json.dump(failures, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Data collection complete!")
    print(f"Successfully fetched: {len(corpus_index)}/{len(companies)} companies")
    if failures:
        print(f"Failures ({len(failures)}) — see data/metadata/fetch_failures.json for exact reasons:")
        for f_ in failures:
            print(f"  - {f_['ticker']}: {f_['reason']}")
    print(f"Corpus index saved to: data/metadata/corpus_index.json")


if __name__ == "__main__":
    main()