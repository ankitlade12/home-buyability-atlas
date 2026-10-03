# Home Buyability Atlas

Reproducible county-level analysis of mortgage payment burden, upfront purchase capital, and uncertainty using public U.S. housing and income data. Target venue: **COMNETSAT 2026, Data Science & Artificial Intelligence**.

**Status:** working research paper and verified descriptive analysis. The manuscript still needs full-text related-work assessment, and resolution of conflicting venue page limits. It does not estimate household mortgage eligibility or causal policy effects.

## Start here

- [IEEE manuscript source](paper/draft.tex)
- [IEEE A4 PDF](outputs/comnetsat2026_buyability_a4.pdf) — generated locally, four pages
- [Editable Word review copy](outputs/home_buyability_review.docx) — generated locally; not an IEEE Word template
- [Interactive county explorer](outputs/buyability_explorer.html) — generated standalone HTML
- [EDAS title, abstract, keywords and topics](paper/edas_submission.json)
- [Venue requirements](paper/venue_requirements.json) and [research audit](paper/research_audit.csv)
- [Detailed methods, findings and research history](docs/research-notes.md)

Generated outputs and source data are excluded from Git. The output links above become available after the corresponding build.

## Reproduce the analysis

Use Python 3.14 (the tested version). Run commands from the repository root.

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

The source manifest fixes the analyzed data vintage. Zillow and other live download URLs can change. The audit will reject a different vintage rather than silently claim exact replication. Preserve cached raw files; do not overwrite the frozen manifest merely to make an audit pass. Data redistribution terms have not yet been reviewed for a public archival release.

## Build the paper

Install a TeX distribution containing `pdflatex`, `bibtex`, and the standard `amsmath`, `booktabs`, `graphicx`, and `url` packages. The unmodified IEEEtran class and bibliography style are included with upstream notices in `paper/template/`.

```sh
.venv/bin/python -m pip install -r requirements-paper.txt
.venv/bin/python scripts/build_paper.py
.venv/bin/python scripts/export_word.py
```

The manuscript uses figures created by `evaluate_representation.py`; build the analysis first. The PDF builder runs LaTeX/BibTeX, rejects layout overflow and unresolved references, and checks font embedding, annotations and bookmarks. Build files stay under `outputs/latex/`. These checks are not IEEE PDF eXpress certification.

A4 is the current default because COMNETSAT's final-manuscript section specifies A4. If EDAS or the organizers confirm US Letter instead:

```sh
.venv/bin/python scripts/build_paper.py --paper-size letter
```

COMNETSAT links to the [IEEE conference templates](https://www.ieee.org/conferences/publishing/templates.html). Its [submission page](https://comnetsat.org/submissions/) conflicts on page count and paper size. The supplied EDAS form independently confirms that manuscripts must not have page numbers, headers or footers. Do not treat the formatted draft as ready to submit until those remaining requirements are resolved.

## Repository layout

| Directory | Contents |
|---|---|
| `paper/` | Manuscript, bibliography, template, venue metadata, audit ledger |
| `scripts/` | Data retrieval, analysis, checks and document builds |
| `sql/` | DuckDB payment calculation |
| `visualization/` | Offline explorer HTML source |
| `provenance/` | Frozen source manifest and conference-page snapshots |
| `integration/` | Candidate NexaMap rendering patch; integration not yet verified |
| `docs/` | Detailed research notes |
| `data/` | Cached raw data and derived tables; ignored by Git |
| `outputs/` | Generated figures, explorer, manuscripts and private review reports; ignored by Git |

`outputs/archive/` retains earlier drafts. Local environments, browser tools, third-party checkouts, downloaded conference HTML snapshots and caches are ignored. Conference URLs and snapshot hashes remain in the provenance manifest. No paper has been submitted by this workflow.

## Interpretation and coverage

The common representation sample contains 3,036 counties. Replacing all-household income with renter income moves 1,682 counties above the 28% comparison benchmark; adding lower-bound tax and insurance proxies moves another 424 above it. These are changes in a constructed measure, not observations of mortgage rejection. The sample contains 98.85% of ACS renter households; the historical renter sample contains 90.74%.

Rates and down payments are explicit scenarios. County medians do not identify a matched household and available property. Insurance-bin bounds and income margins of error describe different limitations. Missing values remain distinct from unbounded costs. Raw observations, assumptions, exclusions and unresolved research issues are documented in the audit and research notes.

## Publication and licensing

GitHub repository: **[ankitlade12/home-buyability-atlas](https://github.com/ankitlade12/home-buyability-atlas)**. No license for original code is granted by this README; a project license remains to be chosen. Bundled IEEEtran files retain their upstream notices, and the IEEE citation style retains its upstream license metadata. Source datasets retain their providers' terms. Grammarly reports and earlier manuscript versions are excluded from Git.
