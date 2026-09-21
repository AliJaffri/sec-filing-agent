import streamlit as st
import pandas as pd

from sec_client import (
    lookup_company,
    get_submissions,
    filter_filings,
    build_filing_url,
    download_filing,
    html_to_text,
    make_filename,
    create_zip,
)


st.set_page_config(
    page_title="SEC Filing Agent",
    page_icon="📄",
    layout="wide"
)


st.title("SEC Filing Agent")

st.write(
    """
    Search, retrieve, and download SEC filings directly
    from EDGAR.
    
    Supported forms include **10-K, 10-Q, and 8-K**.
    """
)


# --------------------------
# SIDEBAR
# --------------------------

with st.sidebar:

    st.header("Search Settings")

    ticker = st.text_input(
        "Ticker",
        value="AAPL"
    ).upper().strip()

    forms = st.multiselect(
        "Filing Type",
        [
            "10-K",
            "10-Q",
            "8-K"
        ],
        default=["10-K"]
    )

    current_year = pd.Timestamp.today().year

    start_year = st.number_input(
        "Start Year",
        min_value=1994,
        max_value=current_year,
        value=max(1994, current_year - 5)
    )

    end_year = st.number_input(
        "End Year",
        min_value=1994,
        max_value=current_year,
        value=current_year
    )

    max_results = st.slider(
        "Maximum Results",
        min_value=1,
        max_value=100,
        value=20
    )

    search_button = st.button(
        "Search SEC",
        type="primary",
        use_container_width=True
    )


# --------------------------
# SEARCH
# --------------------------

if search_button:

    if not ticker:

        st.error(
            "Enter a ticker symbol."
        )

        st.stop()

    if not forms:

        st.error(
            "Select at least one filing type."
        )

        st.stop()

    try:

        with st.spinner(
            f"Searching SEC EDGAR for {ticker}..."
        ):

            company = lookup_company(ticker)

            submissions = get_submissions(
                company["cik"]
            )

            filings = filter_filings(
                submissions,
                forms=forms,
                start_year=int(start_year),
                end_year=int(end_year)
            )

            filings = filings.head(
                max_results
            )

        st.session_state["company"] = company
        st.session_state["filings"] = filings

    except Exception as e:

        st.error(
            f"SEC search failed: {e}"
        )


# --------------------------
# RESULTS
# --------------------------

if (
    "company" in st.session_state
    and
    "filings" in st.session_state
):

    company = st.session_state["company"]

    filings = st.session_state["filings"]

    st.subheader(
        company["title"]
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Ticker",
        company["ticker"]
    )

    col2.metric(
        "CIK",
        company["cik"]
    )

    col3.metric(
        "Filings Found",
        len(filings)
    )

    if filings.empty:

        st.warning(
            "No filings matched your search."
        )

        st.stop()


    display_columns = [
        "filingDate",
        "reportDate",
        "form",
        "accessionNumber",
        "primaryDocument"
    ]

    st.dataframe(
        filings[display_columns],
        use_container_width=True,
        hide_index=True
    )


    st.divider()

    st.subheader(
        "Download Individual Filings"
    )


    for index, row in filings.iterrows():

        filing_date = str(
            row["filingDate"].date()
        )

        form = row["form"]

        accession = row[
            "accessionNumber"
        ]

        primary_document = row[
            "primaryDocument"
        ]

        filing_url = build_filing_url(
            company["cik"],
            accession,
            primary_document
        )


        with st.expander(
            f"{form} — {filing_date}"
        ):

            st.write(
                f"**Report date:** "
                f"{row['reportDate']}"
            )

            st.write(
                f"**Accession:** "
                f"{accession}"
            )

            st.link_button(
                "View on SEC EDGAR",
                filing_url
            )


            try:

                html_bytes = download_filing(
                    filing_url
                )

                html_filename = make_filename(
                    ticker,
                    form,
                    filing_date,
                    "html"
                )

                st.download_button(
                    "Download HTML",
                    data=html_bytes,
                    file_name=html_filename,
                    mime="text/html",
                    key=f"html_{index}"
                )


                text = html_to_text(
                    html_bytes
                )

                text_filename = make_filename(
                    ticker,
                    form,
                    filing_date,
                    "txt"
                )

                st.download_button(
                    "Download Clean Text",
                    data=text.encode(
                        "utf-8"
                    ),
                    file_name=text_filename,
                    mime="text/plain",
                    key=f"text_{index}"
                )

            except Exception as e:

                st.warning(
                    f"Could not prepare download: {e}"
                )


    # --------------------------
    # BULK DOWNLOAD
    # --------------------------

    st.divider()

    st.subheader(
        "Bulk Download"
    )

    st.write(
        """
        Download all filings returned by your search
        as one ZIP archive.
        """
    )


    if st.button(
        "Prepare ZIP Archive"
    ):

        files = []

        progress = st.progress(0)

        total = len(filings)

        try:

            for counter, (_, row) in enumerate(
                filings.iterrows(),
                start=1
            ):

                filing_date = str(
                    row["filingDate"].date()
                )

                form = row["form"]

                url = build_filing_url(
                    company["cik"],
                    row["accessionNumber"],
                    row["primaryDocument"]
                )

                html = download_filing(
                    url
                )

                html_filename = make_filename(
                    ticker,
                    form,
                    filing_date,
                    "html"
                )

                files.append(
                    (
                        html_filename,
                        html
                    )
                )


                text = html_to_text(
                    html
                )

                text_filename = make_filename(
                    ticker,
                    form,
                    filing_date,
                    "txt"
                )

                files.append(
                    (
                        text_filename,
                        text.encode("utf-8")
                    )
                )


                progress.progress(
                    counter / total
                )


            zip_data = create_zip(
                files
            )


            st.success(
                f"Prepared {total} filings."
            )


            st.download_button(
                "Download ZIP",
                data=zip_data,
                file_name=f"{ticker}_SEC_filings.zip",
                mime="application/zip"
            )


        except Exception as e:

            st.error(
                f"Bulk download failed: {e}"
            )
