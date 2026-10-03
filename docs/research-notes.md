# Methods and interpretation

This project compares county-level mortgage payment burden, upfront capital, and uncertainty. The geographic universe contains 3,144 county equivalents in the 50 states and DC. The baseline joins twelve-month mean 2024 ZHVI to ACS 2020–2024 five-year household and renter-income estimates; 3,062 counties have price/all-household-income matches and 3,043 have renter-income matches.

The baseline assumes a 30-year fixed-rate loan with 20% down. Rates of 3%, 6%, and 7.03% are explicit comparisons on fixed 2024 inputs, not observations of current county mortgage terms. The extended analysis varies down payment and adds ownership-cost proxies. Missing source values remain missing rather than being imputed.

## Source integrity

`provenance/source_manifest.json` fixes the analyzed source vintage. The audit checks all 163 cached input hashes and reconciles SQL and Python calculations. Cached downloads must be preserved for exact reproduction because live sources can be revised. Passing arithmetic checks establishes internal consistency, not household-level validity.

## Extended analysis

### Historical comparison and decomposition

The fetch script downloads official sequence 0058 (B19013) and sequence 0117 (B25119), estimates and MOEs, plus geography records for all 50 states and DC. Column positions are derived from official Excel templates, not guessed offsets. County records are identified by summary level 050 and geographic component 00, then joined to estimates by state and logical record number. This produces 3,142 historical county income records. The Latin-1 source encoding is retained correctly during parsing.

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

Four focused tests cover even-count insurance medians spanning bins, open-ended bins, invalid count inputs and independent monthly loan-balance amortization. The extended build additionally checks county uniqueness, one-to-one joins, the historical county count, 52 PMMS observations per year, decomposition additivity, scenario cardinality and ordered cost bounds. Historical results are checked under three boundary screens. The generated figure was inspected visually.

Additional outputs: `outputs/research_update.html` (standalone report with embedded figure), `outputs/historical_summary.csv`, `outputs/entry_cost_summary.csv`, `outputs/renter_income_uncertainty.csv`, `outputs/historical_coverage_audit.csv`, `data/processed/historical_decomposition_*.csv`, and `data/processed/extended_research_layers.geojson`.

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

## Limits of the evidence

County medians do not identify a matched purchaser and property. Assets, credit scores, other debts, available listings, maintenance, and assistance are not observed. Renter households are not a sample of actual prospective buyers. The benchmark classifications are descriptive comparisons rather than mortgage eligibility decisions.

ACS estimates pool five years; annual ZHVI and mortgage-rate summaries do not make the inputs synchronous. ZHVI is model-derived and retrospectively revised. The historical screen excludes some geographic changes without fully harmonizing boundaries. The common representation sample covers 98.85% of ACS renter households; the historical renter sample covers 90.74%.

Income MOEs, grouped insurance bounds, and financing scenario ranges describe different sources of variation. No joint confidence interval, tax/insurance sampling-error propagation, or home-value uncertainty model is implemented. No participant study establishes usability or improved comprehension. Causal effects, rental displacement, and metropolitan core/periphery comparisons remain outside the completed analysis.
