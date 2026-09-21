import io
import re
import time
import zipfile
import requests
import pandas as pd
from bs4 import BeautifulSoup

SEC_DATA = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

# IMPORTANT:
# Replace this with your real contact information.
HEADERS = {
    "User-Agent": "Academic SEC Filing Research Tool your_email@university.edu",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}

DATA_HEADERS = {
    "User-Agent": "Academic SEC Filing Research Tool your_email@university.edu",
    "Accept-Encoding": "gzip, deflate",
}


def sec_get(url, data_api=False, timeout=30):
    """
    Request helper with basic rate limiting and error handling.
    """
    headers = DATA_HEADERS if data_api else HEADERS

    response = requests.get(
        url,
        headers=headers,
        timeout=timeout
    )

    response.raise_for_status()

    # Be polite to SEC infrastructure
    time.sleep(0.12)

    return response


def get_company_tickers():
    """
    Download SEC's ticker -> CIK mapping.
    """

    url = "https://www.sec.gov/files/company_tickers.json"

    response = requests.get(
        url,
        headers=DATA_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    raw = response.json()

    companies = []

    for _, item in raw.items():

        companies.append({
            "ticker": item["ticker"].upper(),
            "title": item["title"],
            "cik": str(item["cik_str"]).zfill(10)
        })

    return pd.DataFrame(companies)


def lookup_company(ticker):
    """
    Find a company from its ticker.
    """

    ticker = ticker.strip().upper()

    companies = get_company_tickers()

    match = companies[
        companies["ticker"] == ticker
    ]

    if match.empty:
        raise ValueError(
            f"Ticker '{ticker}' was not found in the SEC ticker database."
        )

    return match.iloc[0].to_dict()


def get_submissions(cik):
    """
    Get recent SEC filing history for a CIK.
    """

    cik = str(cik).zfill(10)

    url = f"{SEC_DATA}/submissions/CIK{cik}.json"

    response = requests.get(
        url,
        headers=DATA_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    time.sleep(0.12)

    return response.json()


def filings_dataframe(submissions):
    """
    Convert SEC recent filings into a DataFrame.
    """

    recent = submissions["filings"]["recent"]

    df = pd.DataFrame(recent)

    return df


def filter_filings(
    submissions,
    forms=None,
    start_year=None,
    end_year=None
):
    """
    Filter filings by form and filing year.
    """

    df = filings_dataframe(submissions)

    if forms:
        df = df[df["form"].isin(forms)]

    df["filingDate"] = pd.to_datetime(
        df["filingDate"],
        errors="coerce"
    )

    if start_year:
        df = df[
            df["filingDate"].dt.year >= start_year
        ]

    if end_year:
        df = df[
            df["filingDate"].dt.year <= end_year
        ]

    df = df.sort_values(
        "filingDate",
        ascending=False
    )

    return df


def build_filing_url(cik, accession_number, primary_document):
    """
    Construct the SEC archive URL for a filing.
    """

    cik_no_zeros = str(int(cik))

    accession_clean = accession_number.replace("-", "")

    return (
        f"{SEC_ARCHIVES}/"
        f"{cik_no_zeros}/"
        f"{accession_clean}/"
        f"{primary_document}"
    )


def download_filing(url):
    """
    Download original SEC filing.
    """

    response = sec_get(url)

    return response.content


def html_to_text(html_bytes):
    """
    Convert filing HTML into cleaner plain text.
    """

    soup = BeautifulSoup(
        html_bytes,
        "lxml"
    )

    # Remove scripts/styles
    for element in soup(
        ["script", "style", "noscript"]
    ):
        element.decompose()

    text = soup.get_text("\n")

    # Clean excessive whitespace
    text = re.sub(
        r"\n\s*\n+",
        "\n\n",
        text
    )

    return text.strip()


def make_filename(ticker, form, filing_date, extension):
    """
    Generate consistent filenames.
    """

    clean_form = form.replace("/", "-")

    return (
        f"{ticker}_"
        f"{clean_form}_"
        f"{filing_date}."
        f"{extension}"
    )


def create_zip(files):
    """
    Create ZIP archive in memory.

    files:
        list of tuples:
        (filename, bytes)
    """

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zf:

        for filename, content in files:

            zf.writestr(
                filename,
                content
            )

    buffer.seek(0)

    return buffer.getvalue()
