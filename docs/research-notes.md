# County home buyability research

This repository starts a reproducible, real-data study of geographic barriers to entering homeownership. The current output is a **descriptive payment-burden pilot**, not a finished paper, an underwriting model, or evidence of a causal inflation effect. No synthetic household observations are used.

The second phase now adds an observed-rate historical comparison, entry-capital scenarios, local tax/insurance proxies and uncertainty checks. Start with [`outputs/research_update.html`](outputs/research_update.html) for the generated results report. The original pilot below remains separately reproducible.

Working title: **The Geography of Entry into Homeownership: Mortgage Payment Burdens and Upfront Capital Requirements Across U.S. Counties**.

## Run the pilot

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_data.py
.venv/bin/python scripts/build_baseline.py
.venv/bin/python scripts/fetch_data.py --extended
.venv/bin/python scripts/test_analysis.py
.venv/bin/python scripts/extend_analysis.py
```

Raw downloads are cached. Their URLs, SHA-256 hashes, sizes and local timestamps are in `data/raw/manifest.json`. To preserve reproducibility, archive this manifest with the exact input files; Zillow revises its historical series. Re-downloading a changed file is a new data vintage. Raw files and generated artifacts are ignored by Git, but are present locally. Review providers' redistribution terms before releasing a replication archive.

| Input | Measure | Use and limitation |
|---|---|---|
| Zillow county ZHVI, middle tier, seasonally adjusted | Typical home value | Average of all 12 monthly 2024 observations; not median transaction price or available inventory |
| ACS 2020–2024 B19013 | All-household median income and margin of error | Period estimate expressed in 2024 dollars; not a point estimate of December 2024 income |
| ACS 2020–2024 B25119, cell 003 | Renter-household median income and margin of error | Better entry-population comparison, but renters are not identical to prospective first-time buyers |
| Census 2024 cartographic county boundaries, 1:500,000 | County/county-equivalent geometry | 50 states and DC; simplified geometry appropriate for national maps |
| Rate scenarios: 3%, 6%, 7.03% | Assumed annual nominal mortgage rates | 7.03% supported by the September 24, 2026 PMMS release; applied to fixed 2024 inputs as a scenario, not a historical 2024 rate |

Primary source documentation: [Zillow](https://www.zillow.com/research/data/), [ACS bulk files](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/), [B25119 definitions](https://api.census.gov/data/2024/acs/acs5/groups/B25119.html), [ACS period estimates](https://www.census.gov/programs-surveys/acs/guidance/estimates.html), [Freddie Mac release](https://freddiemac.gcs-web.com/news-releases/news-release-details/mortgage-rates-average-703/).

The API redirected the unauthenticated Census query to a missing-key page, so this implementation uses official bulk summary tables. An attempted FRED rate download returned HTML and then an alternative URL returned 404; no historical mortgage-rate series is used. The PMMS release was readable through web research but its local download returned 403. Do not treat the web-verified scenario rate as an archived time series.

## Outputs and checks

- `data/processed/buyability.duckdb`: computed scenario table.
- `data/processed/buyability_scenarios.csv`: county by rate scenario; GEOIDs must be read as strings.
- `data/processed/buyability_2024_rate_scenario.geojson`: WGS84 polygons for mapping, including missing counties.
- `outputs/county_coverage_audit.csv`: universe, inclusion decisions and missingness.
- `outputs/zillow_unmatched_geographies.csv`: Zillow GEOIDs outside the boundary universe; inspect before making national coverage claims.
- `outputs/scenario_summary.csv`: equally weighted county summaries; not household-weighted national affordability rates.
- `outputs/baseline_summary.json`: assumptions, coverage and completed numerical checks.
- `outputs/payment_burden_pilot.png` and `.pdf`: two-panel contiguous-U.S. map. Alaska and Hawaii remain in the data.

The build requires unique county keys, one-to-one joins and twelve price observations; checks loan amortization with an independent monthly balance recurrence; verifies monotonicity in rates and the uniform multiplicative rate effect. ACS negative sentinel values are converted to missing values. No missing county values are interpolated. Income-MOE bounds are sensitivity bounds only: they omit price uncertainty and are not joint confidence intervals. Renter-income MOEs are retained for subsequent sensitivity analysis.

## Research assessment

Initial run: 3,062 of 3,144 county equivalents have valid all-household income and complete 2024 ZHVI; 3,043 also have valid renter income. There are 81 missing/incomplete ZHVI matches and one additional invalid/missing all-household income. All eight unmatched Zillow geographies are legacy Connecticut counties, while the Census universe uses planning regions. Connecticut requires explicit geography harmonization before comprehensive national claims.

| Fixed-input rate scenario | Median county P&I / all-household income | Median county P&I / renter income |
|---|---:|---:|
| 3.00% | 13.95% | 23.34% |
| 6.00% | 19.84% | 33.19% |
| 7.03% | 22.08% | 36.94% |

These are medians across eligible counties, with different valid sample sizes for the two income measures; they are not national household burdens. Holding principal and term fixed, the move from 3% to 7.03% increases P&I by 58.28% in every county. The empirical contribution must go beyond this mechanical result.

The motivating question matters, but renaming a mortgage affordability ratio is not a sufficient research contribution. NAR already uses mortgage payments, income and a 20% down payment in its [Housing Affordability Index](https://www.nar.realtor/research-and-statistics/housing-statistics/housing-affordability-index/methodology). Distinguish this project through entrant-focused income measures, explicit upfront capital requirements, local non-mortgage costs, geographic comparisons and reproducible uncertainty analysis.

The original abstract states findings before analysis. Replace “analyses show” and “results suggest” with research questions until the corresponding estimates exist. The pilot does not test metro-core divergence, rental displacement, supply restrictions or lock-in.

### What the original formula identifies

Let V be typical home value, Y annual income, d the down-payment share and a(r) the monthly 360-payment amortization factor. Then:

`PI_ratio(c,r) = 12 × (1-d) × V(c)/Y(c) × a(r)`.

For common d and r, the county ranking is exactly the ranking of V/Y. Changing a common rate from r0 to r1 multiplies every county ratio by the same `a(r1)/a(r0)`. Absolute percentage-point increases differ because starting V/Y differs. Therefore a map of the rate difference does not by itself discover heterogeneous causal policy effects. It measures heterogeneous absolute exposure under fixed inputs. Threshold crossings can change even when rankings do not.

### Define the outcome honestly

Use two separately reported dimensions instead of an arbitrary weighted index:

1. **Recurring payment burden:** `(principal + interest + property tax + homeowners insurance + mortgage insurance + HOA) / monthly gross income`. Maintenance and utilities belong in a separate broader ownership-cost sensitivity measure.
2. **Entry capital requirement:** down payment plus closing costs and required reserves, in dollars and relative to annual income. A ratio to income is not observed saving time or a measure of liquid wealth.

The pilot computes only principal and interest and the 20% down-payment/income ratio. It does not yet estimate full housing costs. The [CFPB toolkit](https://www.consumerfinance.gov/documents/5982/cfpb_your-home-loan-toolkit.pdf) describes 28% as a rule of thumb for total monthly home payment. A P&I-only ratio above 28% already exceeds that benchmark before other costs, but a ratio below it does not establish affordability. Use “above the specified burden benchmark,” not “unbuyable.” Mortgage approval also depends on other debts, assets, credit and loan products.

ZHVI is a modeled typical home value. [FHFA HPI](https://www.fhfa.gov/data/hpi) measures price changes and cannot be substituted directly as a dollar purchase price. A repeat-sales index could be used for robustness after anchoring a dollar level and documenting the anchoring assumptions.

### Inflation and identification

National inflation is common across counties. A one-date county cross-section cannot identify its effect separately from the mortgage-rate environment. In a panel with time fixed effects, the common national inflation series is absorbed by those effects. Adding CPI and calling its coefficient a local causal effect is not valid.

Further, dividing both nominal home values and nominal incomes by the same CPI leaves V/Y unchanged. Showing a separately identified inflation channel requires measuring changes in residual household budgets, nonhousing expenses, wages, wealth or exposure to inflation. Public ACS income is not disposable income, and a uniform assumed saving rate would be a scenario rather than observed household behavior.

Use a historical descriptive decomposition of changing prices, incomes and rates as the main feasible study. A Shapley decomposition across all six orders of three-factor changes can allocate their arithmetic contributions without attributing causality. Freeze down-payment assumptions and define time aggregation in advance. Compare non-overlapping ACS windows (for example 2015–2019 versus 2020–2024), acknowledging period estimates and harmonizing county changes, especially Connecticut's planning regions. Do not manufacture monthly income precision from annual/period data.

A causal monetary-policy paper would require an independently defended shock measure, predetermined local exposure, a credible comparison strategy and dynamic diagnostics. The same mortgage-rate variable used to construct the outcome is not independent evidence of policy transmission. Mortgage rates also reflect mortgage spreads and market expectations, so the Treasury channel should not be presented as a complete pricing equation.

### Spatial design

Define metropolitan areas using an official, frozen OMB/Census delineation. County centroids and arbitrary rings alone are a weak representation of access to metropolitan jobs. Large counties can span both a core and its periphery; metro areas can be polycentric.

Treat 0–25 and 25–75 mile bands as sensitivity analyses. Use geodesic distances or an appropriate projected CRS, never degree buffers. At tract resolution, population-weight the intersections; at county resolution, report centroid-assignment limitations and compare alternative classifications. Do not use 25-mile circles to claim tract-level precision from county data. Compare within metros, include uncertainty and account for spatial dependence. Report both equally weighted and household-weighted summaries, using actual household counts for the latter.

Supply constraints require an independent measure, such as a documented supply-elasticity or regulatory/geographic constraint dataset. A high payment ratio cannot establish that a county is supply constrained.

### Rental spillover and lock-in

These are hypotheses or contextual mechanisms until separately tested. Rental spillover needs rental outcomes over time (for example ZORI where available), migration or demand evidence, appropriate geographic aggregation and controls for employment and supply. Adjacent expensive counties alone do not demonstrate displaced demand. Do not copy metro rent values into counties and treat them as independent observations.

Lock-in requires outstanding-loan rates or a defensible exposure proxy plus turnover/inventory evidence. Prior work already establishes this as a research field: [FHFA geographic lock-in analysis](https://www.fhfa.gov/blog/statistics/the-geography-of-the-lock-in-effect-which-msas-are-most-locked-in). Cite existing findings as background rather than claiming our payment index estimates lock-in.

## NexaMap and the submission

The [candidate NexaMap repository](https://github.com/vkondepati/nexamap) documents GeoJSON, DuckDB, styling and buffer operations. These are documented capabilities, not functionality verified in this project. Confirm the intended repository, pin a commit/release, load the generated GeoJSON and check feature counts, values, legends and distance units. Use fixed legend breaks across scenarios. Keep the calculations executable outside the GUI. Record screenshots, software version and exact analysis settings before stating that analyses were performed in NexaMap.

The provided [EDAS link](https://edas.info/N35250?c=35250) was inaccessible during research. Conference identity, track fit, page limit, deadline, review anonymity and template remain unverified. Nothing has been submitted. Do not infer the venue from the EDAS identifier.

If this is a GIS/software venue, the contribution needs a reproducible spatial workflow and an evaluation of the software's analytical capabilities. If it is an economics/housing venue, identification, measurement and comparison with existing affordability research take priority over the visualization platform.

## Next research gates

1. Confirm the venue and freeze research questions before expanding the analysis.
2. Review the pilot's coverage and geography exclusions; add household weights and renter-income sensitivity bounds.
3. Source and document property taxes and insurance. Existing-owner tax bills may understate new-purchaser assessments; ratios of medians are only proxies. Do not invent county premiums. If data cannot support full costs, keep a narrower P&I study and explicitly labeled cost scenarios.
4. Add 5%, 10% and 20% down-payment scenarios with justified mortgage-insurance and rate assumptions. PMMS's excellent-credit, 20%-down population does not represent every entrant.
5. Build a harmonized historical comparison and arithmetic decomposition; add inflation as mechanism/context unless an independent empirical design is supported.
6. Add official metro classifications and spatial robustness checks. Keep rental spillovers outside the main claim unless suitable data and identification are obtained.
7. Complete a systematic prior-work review; write the results and abstract only after these analyses pass review.

## Extended analysis completed October 2, 2026

The extensions address gates 2–5 in part; the historical sample uses a documented comparability screen rather than full geography harmonization. Conference verification, metropolitan comparisons, NexaMap execution and a systematic prior-work review remain outstanding. The historical rate download problem described above was resolved using the [official Freddie Mac workbook](https://www.freddiemac.com/pmms/docs/historicalweeklydata.xlsx). No FRED HTML/error payload is used.

### Historical comparison and decomposition

The 2019 Census API requires a key. Instead, the fetch script downloads official sequence 0058 (B19013) and sequence 0117 (B25119), estimates and MOEs, plus geography records for all 50 states and DC. Column positions are derived from official Excel templates, not guessed offsets. County records are identified by summary level 050 and geographic component 00, then joined to estimates by state and logical record number. This produces 3,142 historical county income records. The Latin-1 source encoding is retained correctly during parsing.

Use 2019 and 2024 twelve-month mean ZHVI, five-year ACS income estimates for non-overlapping windows, and the annual mean of 52 weekly PMMS rates in each year. Rates are 3.93577% and 6.72115%. These averages are entered into the amortization formula; this is not the same estimand as averaging all monthly realized purchaser payments. The [2022 PMMS methodology change](https://www.freddiemac.com/research/insight/20221103-freddie-macs-newly-enhanced-mortgage-rate-survey) is a comparability limitation. Applying a common conforming-market benchmark across all counties does not capture local mortgage pricing, jumbo pricing, credit variation, or Alaska/Hawaii-specific pricing.

For common GEOIDs, compare 2019 and 2024 cartographic boundaries in EPSG:6933. Retain relative symmetric-difference area at or below 1%. This may exclude shoreline/generalization changes as well as administrative changes; it does not certify perfectly unchanged boundaries. Connecticut stays excluded; we do not interpolate medians across its incompatible boundaries. Of the 3,062 baseline counties, 88 lack complete 2019 ZHVI and 49 fail the geometry screen. There are 2,925 retained counties; 2,912 have usable renter income at both endpoints.

| Population measure | Median county P&I burden, 2019 | Median county P&I burden, 2024 | Counties with increase |
|---|---:|---:|---:|
| All-household income | 13.91% | 21.42% | 98.36% |
| Renter-household income | 22.94% | 35.91% | 96.12% |

All loans assume 20% down and 30 years. Median differences need not equal the median of county differences. The Shapley accounting decomposition averages all six orders of updating nominal prices, nominal incomes and rates, with an exact county-level add-up check. Mean contributions in percentage points are:

| Population measure | Home values | Nominal income | Mortgage rate | Total mean change |
|---|---:|---:|---:|---:|
| All-household | +7.14 | −4.83 | +5.92 | +8.23 |
| Renter-household | +11.67 | −7.83 | +9.72 | +13.55 |

These are arithmetic allocations, not causal effects. Nominal price and income components contain inflation and other changes; they are not separate inflation estimates. Cross-year allocations depend on the dollar convention, which here is the nominal dollars of each endpoint year. Price and income levels use period summaries, not the same set of observed individual buyers.

The 0.5%, 1% and 2% geometry screens produce all-household mean increases of 8.21, 8.23 and 8.23 percentage points, respectively; renter increases are 13.54, 13.55 and 13.55. See `outputs/boundary_screen_sensitivity.csv` for sample sizes.

### Entry-cost scenarios

New observed inputs are ACS B25003 household/renter counts; B25103 cell 002 median annual real-estate taxes for mortgaged owner-occupied units; and B25141 cells 003–014 insurance-cost bins for mortgaged homes. Exact table definitions: [tax](https://api.census.gov/data/2024/acs/acs5/groups/B25103.html), [insurance](https://api.census.gov/data/2024/acs/acs5/groups/B25141.html).

The insurance interval spans the bins containing the central observation(s) of the estimated county count distribution. No within-bin interpolation is used. The open-ended $4,000+ bin remains unbounded above. This is a grouped-data bound, not a sampling confidence interval. We use the upper edges of closed bins conservatively (for example $1,500 for the $1,000–$1,499 bin). Census tax median codes 199 and 10001 are also treated as intervals, below $200 and at least $10,000; see the [Census summary-file code definitions](https://www2.census.gov/programs-surveys/acs/summary_file/2008/documentation/1_year/ACS_2008_SF_Tech_Doc.pdf). In the baseline geography sample, 19 tax medians are top-coded and two insurance intervals have an open upper endpoint. The raw coded values are retained for auditing.

Scenario choices, rather than observed borrower terms:

- Down payment: 5%, 10% or 20%.
- Mortgage rate: 7.03%; a separate +0.50 percentage-point sensitivity is an analyst-selected stress, not an estimated LTV/credit premium.
- PMI below 20% down: $30–$70 per month per $100,000 of initial principal, from [Freddie Mac's consumer range](https://myhome.freddiemac.com/buying/breaking-down-pmi). This models initial payments, not lifetime PMI costs, and is not a credit-specific quote.
- Closing costs: 2–5% of value, from [Freddie Mac](https://myhome.freddiemac.com/blog/homebuying/what-are-closing-costs-and-how-much-will-i-pay). Prepaids are included in this broad range; insurance is not separately added again to upfront cash. Lender credits, assistance, gifts and reserves are not estimated.

These produce 18,372 county-scenario rows. The 7.03% renter summaries below use a common 3,036-county sample with valid income and cost inputs:

| Down payment | Median county monthly cost proxy / renter income | Median county upfront cash / annual renter income |
|---|---:|---:|
| 5% | 53.6–57.3% | 40.4–57.7% |
| 10% | 51.1–54.8% | 69.2–86.5% |
| 20% | 44.5–45.7% | 126.9–144.2% |

Costs are constructed from P&I plus existing-owner tax and insurance proxies and scenario PMI. Adding separate medians does not yield an observed median total bill. Tax reassessment and insurance repricing can change purchaser costs; HOA, maintenance, utilities and nonhousing debt are omitted. Ranges mix grouped-data limits with explicit assumption ranges and are not confidence intervals. Twenty renter-sample counties have unbounded upper cost proxies; the median across counties remains finite. CSV/DuckDB use infinity for those upper bounds; GeoJSON uses null with an explicit `cost_upper_unbounded` flag.

The summary also includes household-weighted county exposure. This is the fraction of households living in counties whose constructed ratio exceeds the benchmark, **not the fraction of households that cannot buy**. The cash/income measure does not observe assets and cannot be interpreted as years needed to save.

### Income uncertainty and verification

For the original P&I-only 7.03% / 20%-down scenario, transform renter median income plus/minus its reported ACS MOE while holding price fixed. If the lower income endpoint is nonpositive, the upper burden endpoint is unbounded. There are 1,924 counties above 28% throughout this income range, 258 below throughout, 861 straddling, and 19 without valid inputs. These are income-only sensitivity classifications, not simultaneous confidence statements across counties and not full-cost classifications.

Four focused tests cover even-count insurance medians spanning bins, open-ended bins, invalid count inputs and independent monthly loan-balance amortization. The extended build additionally checks county uniqueness, one-to-one joins, the historical county count, 52 PMMS observations per year, decomposition additivity, scenario cardinality and ordered cost bounds. Historical results are checked under three boundary screens. Figure inspected visually; NexaMap GUI verification is still outstanding.

Additional outputs: `outputs/research_update.html` (standalone report with embedded figure), `outputs/historical_summary.csv`, `outputs/entry_cost_summary.csv`, `outputs/renter_income_uncertainty.csv`, `outputs/historical_coverage_audit.csv`, `data/processed/historical_decomposition_*.csv`, and `data/processed/extended_research_layers.geojson`.

## Submission positioning following the supplied topic list

The user supplied these venue topics: Big Data, Data Mining, Fuzzy Logic, Artificial Neural Networks, Cloud and Distributed Computing, Deep Learning Algorithms, Optimization Algorithms, Bayesian Models and Methods, Data Representation and Visualization, Support Vector Machines, and Quantum Computing. These establish a computing-oriented scope; they do not establish the conference identity, deadline, template or acceptance criteria.

Proposed primary topic: **Data Representation and Visualization**. Secondary topic: **Data Mining**, conditional on completing substantive spatial pattern analysis. Current draft title: **Mapping Home Buyability: Comparing Payment Burden, Entry Capital, and Uncertainty Across U.S. Counties**. The offline interactive prototype and representation comparisons are now implemented; no participant evaluation has been conducted.

The scientific focus shifts to how a reproducible representation of heterogeneous public data helps distinguish payment burdens, capital requirements, and uncertainty across places and financing scenarios. Housing provides the application. The current county dataset does not justify a Big Data or distributed-computing claim. A deterministic mortgage formula does not require an ANN, SVM or deep-learning predictor, and fitting one to the formula's own output would not establish predictive validity.

### Proposed contribution and evaluation

1. Represent buyability through two explicit dimensions: recurring cost/income and upfront cash/income. Retain missingness, income MOEs, cost intervals and open-ended categories as distinct states rather than collapsing them into a binary eligibility label.
2. Implement coordinated views: geographic distributions, a payment-versus-capital scatterplot, scenario comparisons and historical accounting contributions. Use fixed comparison scales and visible source vintages. Implement and verify these in a pinned NexaMap version, or document exactly which operations run externally.
3. Evaluate against the original P&I/all-household-income choropleth on a common county sample. Compare all-household versus renter income; P&I versus tax/insurance-inclusive proxies; and point estimates versus uncertainty-aware classifications. Report changes in rankings and threshold classifications without claiming one measure is verified household eligibility.
4. Test spatial patterns with official metropolitan classifications and an explicit spatial-neighbor definition. If using local statistical tests, account for multiple comparisons and spatial dependence. These analyses describe geographic structure; they do not identify rental displacement or causal monetary-policy effects.
5. Evaluate numerical agreement with the independent payment calculation, geography-join completeness, preservation of missing/unbounded values, stability under assumptions, and measured end-to-end runtime on stated hardware. Runtime is a reproducibility characteristic, not evidence of a new scalable algorithm. Claims of better user understanding require a separately designed user evaluation; without one, report case studies and analytical capabilities only.

The main research questions are: (a) How does representing both payment and entry-capital requirements change county comparisons relative to the original index? (b) Which geographic patterns and benchmark classifications persist across income populations, financing scenarios and uncertainty ranges? (c) Can the computational and visualization workflow preserve the source data's limitations while making the comparisons reproducible?

A working manuscript follows this structure in `paper/draft.tex`, with `paper/references.bib`. A map plus an established affordability formula is insufficient on its own: the representation, analytical workflow and evaluation must provide a defensible contribution. No claim of a new visualization technique, validated usability, or completed NexaMap evaluation is currently supported.

## Implemented representation evaluation

Run `.venv/bin/python scripts/evaluate_representation.py` after the baseline and extended builds. Open `outputs/buyability_explorer.html` directly in a browser; it embeds the real county inputs and simplified geometry and needs no server. Two coordinated maps, a capital/payment scatterplot, county inspection, scenario controls, uncertainty classifications and CSV export distinguish missing values from unbounded upper values. Alaska and Hawaii are included in summaries and the selector, but not the contiguous-U.S. display maps.

At 7.03% and 20% down:

| Comparison | Common counties | Spearman correlation | Highest-decile retention | Cross upward over 28% |
|---|---:|---:|---:|---:|
| All-household to renter income | 3,043 | 0.868 | 71.1% | 1,685 |
| Renter P&I to lower cost proxy | 3,036 | 0.981 | 88.8% | 424 |
| Original to renter lower cost proxy | 3,036 | 0.818 | 65.8% | 2,106 |

These compare representations, not predictive accuracy or observed mortgage rejections. Do not add transition counts across different samples. `outputs/representation_transitions.csv` also evaluates 25%, 30% and 36%. Top-decile sets use ceiling(0.1 × sample size), with GEOID breaking ties; rank correlations use average tied ranks. The single-run timing in `representation_evaluation.json` covers comparison and figure generation, not full-pipeline performance or a scalability benchmark.

Browser verification compared all 18,372 financing rows under both income populations with Python CSV outputs: 36,744 scenario/population rows, 183,720 value checks, maximum finite absolute difference 1.78e-15. Missing and unbounded classifications were checked separately. Four numerical unit tests also pass. GeoJSON censoring flags were corrected to nullable booleans after a merge had serialized them as strings; verification confirms 19 tax-top-code flags, two open insurance flags and 20 unbounded-cost flags survive export.

NexaMap checkout: `vkondepati/nexamap` commit `b468d6afcf196804a7570e669f616352f74db1f1`, under ignored `vendor/nexamap`. Initial UI import retained 3,144 features but rendered projected meters as longitude/latitude. `integration/nexamap-rendering.patch` adds a Leaflet coordinate converter for the imported layer. The browser session reset before the patched import could be verified; this remains a candidate fix, not a validated integration. Printing, editing, buffering and native choropleth styling are outside the completed verification. The standalone explorer is the evaluated visualization artifact.

## Targeted related-work assessment

This initial primary-source search is not a systematic review. The paper's contribution is an applied representation comparison, not the invention of mortgage affordability ratios or uncertainty visualization.

| Source | Evidence reviewed | Overlap and implication |
|---|---|---|
| [NAR Housing Affordability Index](https://www.nar.realtor/research-and-statistics/housing-statistics/housing-affordability-index/methodology) | Official methodology | Financing, price and income are established inputs; our core formula is not novel. |
| [HomeSeeker, Li et al., 2018](https://baozhifeng.net/publication/journal/ming18vlc/) | Author abstract | Heterogeneous location data and interactive real-estate exploration already exist. Full-text comparison remains necessary. |
| [Lucchesi and Wikle, 2017](https://onlinelibrary.wiley.com/doi/10.1002/sta4.150) | Publisher abstract and bibliographic record | ACS margins of error and areal uncertainty visualization are established. Our interval handling is an application choice, not a new visual encoding. |
| [NAR affordability distribution methodology](https://www.nar.realtor/research-and-statistics/housing-statistics/realtors-affordability-distribution-curve-and-score/methodology) | Official methodology | Distributional affordability and available inventory provide a more demanding comparison than a median-only ratio; our data do not observe listing-level choices. |

Before submission: complete full-text literature comparisons, identify the venue template and deadline, and settle the scope of additional evaluation. Claims of improved understanding require participant evidence; claims about core/periphery patterns require a defined metropolitan geography and spatial analysis. Rental spillover and causal inflation effects are not established by the current results. The manuscript is a working draft, not a submission-ready paper.

## Staff research audit

### Confirmed target venue: COMNETSAT 2026

The user selected IEEE COMNETSAT 2026. The [official homepage](https://comnetsat.org/) confirms Track 5, Data Science and Artificial Intelligence, including Data Representation and Visualization, Incomplete Data, and Data Governance and Metadata Management. Our primary positioning remains an empirical visual-analytics application. The homepage lists Batch 2 full-paper submission October 18, 2026; notification November 6; registration and final manuscript November 18; conference December 3–5 in Manado, Indonesia, advertised as hybrid. Deadline time zone remains unverified. Submission is through EDAS N35250.

The [submission instructions](https://comnetsat.org/submissions/) are internally inconsistent: they state 6–8 pages, a maximum of two pages in the same paragraph, and 4–7 pages later. They also mention both US Letter and A4. A provisional six-page IEEE two-column target fits the two plausible full-paper ranges, but does not resolve the contradiction. The present six-page article-format draft is not equivalent to six IEEE-format pages. Single-blind review and original, unpublished work are stated. The [conference policies](https://comnetsat.org/conference-policies/) use in-person presentation wording despite hybrid/online instructions elsewhere. These conflicts require confirmation before submission or travel arrangements. No organizer has been contacted.

Structured requirements and unresolved questions are in `paper/venue_requirements.json`; fetched official-page snapshots and hashes are retained in `provenance/comnetsat/`. The homepage was retrievable with curl after the web reader returned a gateway error. Older search listings show superseded deadlines and should not override the current official page. Prior statements below that the venue identity is unknown are superseded by this update; scientific gaps remain.

The audit ledger is `paper/research_audit.csv`. Run `.venv/bin/python scripts/audit_research.py` after the analytical builds. Machine-readable findings are in `outputs/research_audit.json`; supporting tables are `audit_common_sample_transitions.csv`, `audit_population_coverage.csv`, and `audit_state_coverage.csv` in that directory.

All 163 raw-file checksums match the frozen `provenance/source_manifest.json`. The downloader now rejects changes to previously recorded content instead of silently replacing its hash. A future intentional data refresh needs a separately retained vintage. Public download links can change, so the frozen manifest identifies the source vintage but cannot guarantee that a future download will reproduce it. Redistribution terms and an archival release remain to be reviewed before sharing the raw data bundle.

The audit found and fixed missing-income uncertainty endpoints being exported as infinity. Missing income/MOE now produces missing endpoints, while a valid interval reaching nonpositive income still has an unbounded upper burden. The existing missing classification was correct; reported counts do not change. A persistent audit assertion checks this distinction.

On the identical 3,036-county complete sample, 1,682 counties cross upward through 28% when income changes, followed by 424 when costs are added, yielding the directly observed combined 2,106. The previously reported 1,685 uses the larger 3,043-county income-only sample and remains correct for that sample. At 25%, one county crosses downward on the income change; renter income should not be assumed lower everywhere.

The baseline covers 98.83% of ACS households and 98.88% of renter households. The complete representation sample covers 98.80% and 98.85%, respectively. The historical renter sample covers 93.92% of households and 90.74% of renters, measured using 2024 household counts. These are coverage diagnostics, not claims that omitted counties are exchangeable with retained ones. Historical exclusion is consequential despite the large county count.

The manuscript now cites source methodology directly, includes the representation figure, and distinguishes model-derived ZHVI from observed transactions. ACS MOEs use the published 90% confidence level; the analysis does not propagate tax/insurance sampling error, uncertainty in insurance-bin counts, or ZHVI error. See [Census MOE definitions](https://www.census.gov/programs-surveys/acs/methodology/sample-size-and-data-quality/sample-size-definitions.html) and [current ZHVI methodology](https://www.zillow.com/research/zhvi-methodology/). Geographic aggregation, prospective-buyer selection and retrospective data revision remain limitations.

Research judgment: this is a reproducible descriptive application with substantive representation sensitivity, but the present evidence does not yet establish a strong visualization-method contribution. Full-text related work and a suitably scoped evaluation are the principal scientific gaps. Software tests do not substitute for user evaluation, and more model complexity would not resolve construct validity. Conference identity, official formatting, author metadata, disclosures and the venue's AI-use policy also remain unresolved. No submission or external publication has been made.
