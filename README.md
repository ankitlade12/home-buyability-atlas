# Home Buyability Atlas

Reproducible county-level analysis of mortgage payment burden, upfront purchase capital, and uncertainty using public U.S. housing and income data.

[Methods and limitations](docs/research-notes.md) · [Source manifest](provenance/source_manifest.json) · [Explorer template](visualization/explorer.html)

## Reproduce

Use Python 3.14 (the tested version) and run from the repository root. Data acquisition requires `curl` and network access.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/fetch_data.py --extended
.venv/bin/python scripts/build_baseline.py
.venv/bin/python scripts/extend_analysis.py
.venv/bin/python scripts/evaluate_representation.py
.venv/bin/python scripts/audit_research.py
.venv/bin/python -m unittest discover -s scripts -p test_analysis.py
```

Open `outputs/buyability_explorer.html` in a browser after building. It works offline and provides county maps, a payment-versus-capital view, scenario controls, county inspection, and CSV export. Display maps cover the contiguous U.S.; summaries and county selection include Alaska and Hawaii.

The source manifest fixes the analyzed vintage. Live download URLs can change, so the audit rejects different source bytes. Preserve cached inputs for exact reproduction; do not overwrite the frozen manifest merely to make an audit pass. Raw data and generated outputs are excluded from Git.

## Results

On 3,036 common counties, replacing all-household income with renter income moves 1,682 counties above the 28% comparison benchmark. Adding lower-bound tax and insurance proxies moves another 424 above it. These are changes in constructed measures, not observations of mortgage rejection. The sample covers 98.85% of ACS renter households; the historical renter sample covers 90.74%.

Rates and down payments are explicit scenarios. County medians do not identify a matched household and available property. Income uncertainty, insurance-bin bounds, missing values, and unbounded costs remain distinct. See the methods for assumptions and limits.

## Repository layout

| Directory | Contents |
|---|---|
| `scripts/` | Data retrieval, analysis, figure generation, and verification |
| `sql/` | DuckDB payment calculation |
| `visualization/` | Offline explorer HTML template |
| `provenance/` | Frozen source manifest |
| `docs/` | Methods, results, and limitations |
| `data/` | Cached raw and processed data; generated locally and ignored |
| `outputs/` | Generated figures, reports, explorer, and audit results; ignored |

The analysis audit verifies cached source hashes, unique scenario keys, SQL/Python agreement, historical additivity, coverage, and nullable censoring flags. The focused tests check insurance-bin handling and loan amortization. These checks establish internal consistency; they do not validate individual mortgage eligibility or causal policy effects.

## Data and licensing

Source datasets retain their providers' terms. Data redistribution terms have not been reviewed for a public archival release. No license for original code is granted by this repository; a project license remains to be chosen.
