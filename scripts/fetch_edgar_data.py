import requests
import json
import csv
import time
from pathlib import Path
from datetime import datetime

# Configuration
BASE_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{}.json"
BASE_XBRL_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{}.json"
BASE_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}"

HEADERS = {
    "User-Agent": "GraphicEraHillUniversity FinancialFilingsProject (student@gehu.ac.in)"
}

TARGET_YEAR = 2022
DELAY_BETWEEN_REQUESTS = 0.2  # 200ms delay

# Setup directories
Path("data/raw/filings").mkdir(parents=True, exist_ok=True)
Path("data/raw/xbrl").mkdir(parents=True, exist_ok=True)
Path("data/metadata").mkdir(parents=True, exist_ok=True)

def fetch_json(url):
    """Fetch JSON from URL with proper headers and error handling."""
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    time.sleep(DELAY_BETWEEN_REQUESTS)
    return response.json()

def fetch_html(url):
    """Fetch HTML content."""
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    time.sleep(DELAY_BETWEEN_REQUESTS)
    return response.text

def get_10k_filing(cik, ticker):
    """
    Find the FY2022 10-K filing for a company.
    Returns: (accession_number, primary_document, filing_date) or None
    """
    submissions_url = BASE_SUBMISSIONS_URL.format(cik)
    print(f"  Fetching submission history for {ticker}...")
    
    data = fetch_json(submissions_url)
    
    # Recent filings are in data['filings']['recent']
    filings = data['filings']['recent']
    
    for i, form in enumerate(filings['form']):
        if form == '10-K':
            filing_date = filings['filingDate'][i]
            # FY2022 10-Ks were mostly filed in Q1 2023 or Q4 2022
            # We look for filings between 2022-01-01 and 2023-06-30
            if '2022' in filing_date or filing_date.startswith('2023'):
                accession = filings['accessionNumber'][i]
                primary_doc = filings['primaryDocument'][i]
                
                print(f"  Found 10-K filed on {filing_date}")
                return accession, primary_doc, filing_date
    
    print(f"  WARNING: No 10-K found for {ticker} in target range")
    return None

def download_filing(cik, ticker, accession, primary_doc):
    """Download the actual 10-K HTML document."""
    # Remove dashes from accession for URL path
    accession_no_dash = accession.replace('-', '')
    # CIK without leading zeros for URL
    cik_clean = str(int(cik))
    
    filing_url = BASE_FILING_URL.format(cik_clean, accession_no_dash, primary_doc)
    print(f"  Downloading filing from {filing_url}")
    
    html_content = fetch_html(filing_url)
    
    output_path = f"data/raw/filings/{ticker}_2022.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  Saved to {output_path}")
    return output_path

def download_xbrl(cik, ticker):
    """Download XBRL company facts JSON."""
    xbrl_url = BASE_XBRL_URL.format(cik)
    print(f"  Downloading XBRL facts from {xbrl_url}")
    
    xbrl_data = fetch_json(xbrl_url)
    
    output_path = f"data/raw/xbrl/{ticker}_xbrl.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(xbrl_data, f, indent=2)
    
    print(f"  Saved to {output_path}")
    return output_path

def main():
    # Read company list
    companies = []
    with open('data/companies.csv', 'r') as f:
        reader = csv.DictReader(f)
        companies = list(reader)
    
    corpus_index = []
    
    print(f"Starting EDGAR data collection for {len(companies)} companies...\n")
    
    for company in companies:
        ticker = company['ticker']
        cik = company['cik']
        name = company['name']
        
        print(f"\n[{ticker}] {name} (CIK: {cik})")
        print("=" * 60)
        
        try:
            # Step 1: Find the 10-K filing
            filing_info = get_10k_filing(cik, ticker)
            
            if not filing_info:
                print(f"  SKIP: Could not find 10-K for {ticker}")
                continue
            
            accession, primary_doc, filing_date = filing_info
            
            # Step 2: Download the filing HTML
            filing_path = download_filing(cik, ticker, accession, primary_doc)
            
            # Step 3: Download XBRL facts
            xbrl_path = download_xbrl(cik, ticker)
            
            # Record in index
            corpus_index.append({
                "ticker": ticker,
                "company_name": name,
                "cik": cik,
                "filing_date": filing_date,
                "accession_number": accession,
                "filing_path": filing_path,
                "xbrl_path": xbrl_path,
                "downloaded_at": datetime.now().isoformat()
            })
            
            print(f"  ✓ Successfully fetched {ticker}")
            
        except Exception as e:
            print(f"  ERROR fetching {ticker}: {str(e)}")
            continue
    
    # Save corpus index
    with open('data/metadata/corpus_index.json', 'w') as f:
        json.dump(corpus_index, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Data collection complete!")
    print(f"Successfully fetched: {len(corpus_index)}/{len(companies)} companies")
    print(f"Corpus index saved to: data/metadata/corpus_index.json")

if __name__ == "__main__":
    main()