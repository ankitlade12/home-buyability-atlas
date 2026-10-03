"""Historical accounting decomposition and observed-cost-proxy scenarios.

All household inputs are public observations. Financing choices are scenarios.
No causal effects, underwriting decisions, or liquid-wealth observations are inferred.
"""
import csv
import io
import itertools
import json
import base64
from zipfile import ZipFile
import numpy as np
import pandas as pd
import geopandas as gpd
import duckdb
from openpyxl import load_workbook
from build_baseline import ROOT, acs, plt
from fetch_data import STATES

RAW, OUT, PROCESSED = ROOT / 'data/raw', ROOT / 'outputs', ROOT / 'data/processed'

def payment_factor(rate):
    rate = np.asarray(rate, dtype=float)
    if np.any(rate <= 0):
        raise ValueError('This analysis uses positive observed/scenario rates')
    return (rate / 12) / (1 - (1 + rate / 12) ** -360)

def insurance_median_interval(counts, total):
    counts = np.asarray(counts, dtype=float)
    if len(counts) != 12 or not np.isfinite(counts).all() or np.any(counts < 0) or not np.isfinite(total) or total <= 0 or not np.isclose(counts.sum(), total):
        return np.nan, np.nan
    low = np.array([0, 100, 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 3500, 4000])
    high = np.array([100, 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 3500, 4000, np.inf])
    cumulative = counts.cumsum()
    lo = np.searchsorted(cumulative, np.floor((total + 1) / 2), side='left')
    hi = np.searchsorted(cumulative, np.floor((total + 2) / 2), side='left')
    return low[lo], high[hi]

def historical_income():
    tables = {'0058': ('B19013_001', 'income'), '0117': ('B25119_003', 'renter_income')}
    template_zip = ZipFile(RAW / 'acs2019_templates.zip')
    indices = {}
    for sequence, (variable, _) in tables.items():
        workbook = load_workbook(io.BytesIO(template_zip.read(f'seq{int(sequence)}.xlsx')), read_only=True)
        columns = next(workbook.active.values)
        indices[sequence] = columns.index(variable)
        assert columns[5] == 'LOGRECNO'
    records = []
    for state in STATES.split(';'):
        abbreviation = state.split()[0].lower()
        with (RAW / f'acs2019/g20195{abbreviation}.csv').open(encoding='latin-1') as f:
            geo = {row[4]: {'geoid': row[9] + row[10], 'name_2019': row[49]}
                   for row in csv.reader(f) if row[2] == '050' and row[3] == '00'}
        for sequence, (_, variable_name) in tables.items():
            with ZipFile(RAW / f'acs2019/20195{abbreviation}{sequence}000.zip') as z:
                for prefix, suffix in [('e', ''), ('m', '_moe')]:
                    filename = f'{prefix}20195{abbreviation}{sequence}000.txt'
                    for row in csv.reader(io.StringIO(z.read(filename).decode('utf-8-sig'))):
                        if row[5] in geo:
                            value = pd.to_numeric(row[indices[sequence]], errors='coerce')
                            geo[row[5]][variable_name + suffix] = value if value >= 0 else np.nan
        records.extend(geo.values())
    result = pd.DataFrame(records)
    assert result.geoid.nunique() == len(result) == 3142
    result.to_csv(PROCESSED / 'income_2019_counties.csv', index=False)
    return result

def historical_analysis(base):
    old = historical_income()
    values = pd.read_csv(RAW / 'zhvi_county.csv', dtype={'StateCodeFIPS': str, 'MunicipalCodeFIPS': str},
                         usecols=lambda c: c.startswith('2019-') or c in ['StateCodeFIPS', 'MunicipalCodeFIPS'])
    months = [c for c in values if c.startswith('2019-')]
    assert len(months) == 12
    values['geoid'] = values.StateCodeFIPS.str.zfill(2) + values.MunicipalCodeFIPS.str.zfill(3)
    values['price_2019'] = values[months].mean(axis=1).where(values[months].notna().all(axis=1))
    old = old.merge(values[['geoid', 'price_2019']], on='geoid', how='left', validate='1:1')
    geo_old = gpd.read_file(RAW / 'counties2019.zip').set_index('GEOID').to_crs(6933)
    geo_new = gpd.read_file(RAW / 'counties2024.zip').set_index('GEOID').to_crs(6933)
    keys = geo_old.index.intersection(geo_new.index)
    left, right = geo_old.loc[keys].geometry, geo_new.loc[keys].geometry
    area_change = left.symmetric_difference(right).area / left.union(right).area
    audit = base[['geoid', 'NAME', 'STATEFP']].merge(old, on='geoid', how='left', validate='1:1')
    audit['boundary_difference_share'] = audit.geoid.map(area_change)
    audit['historical_included'] = ((audit.income > 0) & (audit.price_2019 > 0)
                                    & (audit.boundary_difference_share <= .01))
    audit['historical_exclusion'] = np.select(
        [~(audit.income > 0), ~(audit.price_2019 > 0), audit.boundary_difference_share.isna(), audit.boundary_difference_share > .01],
        ['missing_2019_income_or_geoid', 'incomplete_2019_ZHVI', 'unmatched_boundary', 'boundary_difference_above_1pct'], default='included')
    audit.to_csv(OUT / 'historical_coverage_audit.csv', index=False)
    panel = base.merge(old, on='geoid', suffixes=('_2024', '_2019'), validate='1:1')
    panel_unfiltered = panel.copy()
    panel = panel[panel.geoid.isin(audit.loc[audit.historical_included, 'geoid'])].copy()
    rates = pd.read_excel(RAW / 'pmms_historical.xlsx', skiprows=6, usecols=[0, 1])
    rates.columns = ['date', 'rate_percent']
    rates['date'] = pd.to_datetime(rates.date, errors='coerce')
    rates = rates.dropna()
    assert not rates.date.duplicated().any()
    annual = rates[rates.date.dt.year.isin([2019, 2024])].groupby(rates.date.dt.year).rate_percent.agg(['count', 'mean'])
    assert (annual['count'] == 52).all()
    annual.to_csv(OUT / 'historical_mortgage_rates.csv', index_label='year')
    r0, r1 = annual.loc[2019, 'mean'] / 100, annual.loc[2024, 'mean'] / 100
    sensitivity = []
    for cutoff in [.005, .01, .02]:
        p = panel_unfiltered[panel_unfiltered.geoid.map(area_change) <= cutoff]
        for income_name in ['income', 'renter_income']:
            g = p[(p.price_2019 > 0) & (p[f'{income_name}_2019'] > 0) & (p[f'{income_name}_2024'] > 0)]
            before = .8 * g.price_2019 * payment_factor(r0) * 12 / g[f'{income_name}_2019']
            after = .8 * g.price_2024 * payment_factor(r1) * 12 / g[f'{income_name}_2024']
            sensitivity.append({'boundary_cutoff': cutoff, 'income_population': income_name, 'n_counties': len(g),
                                'mean_change_pp': float(100 * (after-before).mean()), 'share_increased': float((after>before).mean())})
    pd.DataFrame(sensitivity).to_csv(OUT / 'boundary_screen_sensitivity.csv', index=False)
    summary = []
    for income_name in ['income', 'renter_income']:
        p = panel[(panel[f'{income_name}_2019'] > 0) & (panel[f'{income_name}_2024'] > 0)].copy()
        old_values = [p.price_2019.to_numpy(), p[f'{income_name}_2019'].to_numpy(), r0]
        new_values = [p.price_2024.to_numpy(), p[f'{income_name}_2024'].to_numpy(), r1]
        def evaluate(v):
            return .8 * v[0] * payment_factor(v[2]) * 12 / v[1]
        contributions = np.zeros((len(p), 3))
        for ordering in itertools.permutations(range(3)):
            current = list(old_values)
            before = evaluate(current)
            for factor in ordering:
                current[factor] = new_values[factor]
                after = evaluate(current)
                contributions[:, factor] += (after - before) / 6
                before = after
        p['ratio_2019'] = evaluate(old_values)
        p['ratio_2024'] = evaluate(new_values)
        p['change_pp'] = 100 * (p.ratio_2024 - p.ratio_2019)
        for j, label in enumerate(['price', 'income', 'rate']):
            p[f'{label}_contribution_pp'] = 100 * contributions[:, j]
        assert np.allclose(contributions.sum(axis=1), p.ratio_2024 - p.ratio_2019, atol=1e-12)
        p['income_population'] = income_name
        p.to_csv(PROCESSED / f'historical_decomposition_{income_name}.csv', index=False)
        summary.append({'income_population': income_name, 'n_counties': len(p),
                        'median_ratio_2019': p.ratio_2019.median(), 'median_ratio_2024': p.ratio_2024.median(),
                        'share_counties_increased': (p.change_pp > 0).mean(),
                        'mean_change_pp': p.change_pp.mean(),
                        **{f'mean_{label}_contribution_pp': p[f'{label}_contribution_pp'].mean() for label in ['price', 'income', 'rate']}})
    result = pd.DataFrame(summary)
    result.to_csv(OUT / 'historical_summary.csv', index=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ax, row in zip(axes, summary):
        amounts = [row[f'mean_{label}_contribution_pp'] for label in ['price', 'income', 'rate']]
        ax.bar(['Home values', 'Income', 'Mortgage rate'], amounts, color=['#bc5a45', '#39877b', '#567da0'])
        ax.axhline(0, color='#444444', linewidth=.7)
        ax.set_title(f"{'All-household' if row['income_population']=='income' else 'Renter-household'} income\n{row['n_counties']:,} matched counties")
        ax.set_ylabel('Mean contribution, percentage points')
    fig.suptitle('2019 to 2024: arithmetic contributions to P&I burden changes')
    fig.text(.05, .01, 'Shapley allocation across prices, nominal income and rates; 20% down. ACS period incomes. Not causal effects.', fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .95))
    fig.savefig(OUT / 'historical_decomposition.png', dpi=180)
    plt.close(fig)
    return {'rates': {str(y): float(annual.loc[y, 'mean']) for y in [2019, 2024]}, 'results': summary,
            'excluded_from_2024_baseline': int((~audit.historical_included).sum()),
            'boundary_screen': 'relative symmetric-difference area <=1%; cartographic geometry screen, not exact boundary harmonization'}

def cost_analysis(base):
    weights = acs('B25003', {'B25003_E001': 'households', 'B25003_E003': 'renter_households'})
    tax = acs('B25103', {'B25103_E002': 'annual_tax_existing_mortgaged_median', 'B25103_M002': 'annual_tax_moe'})
    # ACS median jam codes are intervals, not exact dollar observations.
    tax['tax_bottom_coded'] = tax.annual_tax_existing_mortgaged_median == 199
    tax['tax_top_coded'] = tax.annual_tax_existing_mortgaged_median == 10001
    tax['annual_tax_low'] = tax.annual_tax_existing_mortgaged_median.mask(tax.tax_bottom_coded, 0).mask(tax.tax_top_coded, 10000)
    tax['annual_tax_high'] = tax.annual_tax_existing_mortgaged_median.mask(tax.tax_bottom_coded, 200).mask(tax.tax_top_coded, np.inf)
    cols = {f'B25141_E{i:03}': f'insurance_bin_{i}' for i in range(2, 15)}
    insurance = acs('B25141', cols)
    # Interval containing the sample median from grouped count estimates. For an even
    # total, include both central observations' bins. No within-bin interpolation.
    bounds = []
    for _, row in insurance.iterrows():
        counts = row[[f'insurance_bin_{i}' for i in range(3, 15)]].to_numpy(dtype=float)
        total = row.insurance_bin_2
        bounds.append(insurance_median_interval(counts, total))
    insurance[['annual_insurance_bin_low', 'annual_insurance_bin_high']] = bounds
    frame = base.merge(weights, on='geoid', how='left', validate='1:1').merge(tax, on='geoid', how='left', validate='1:1')
    frame = frame.merge(insurance[['geoid', 'annual_insurance_bin_low', 'annual_insurance_bin_high']], on='geoid', how='left', validate='1:1')
    frame['insurance_open_upper_bin'] = np.isinf(frame.annual_insurance_bin_high)
    frame.to_csv(PROCESSED / 'observed_cost_proxies.csv', index=False)
    rows = []
    for down in [.05, .10, .20]:
        for rate_spread in [0, .005]:
            s = frame.copy()
            s['down_payment_share'] = down
            s['assumed_rate_spread'] = rate_spread
            s['annual_rate'] = .0703 + rate_spread
            principal = s.price_2024 * (1 - down)
            s['monthly_pi_scenario'] = principal * payment_factor(.0703 + rate_spread)
            for label, pmi_per_100k, closing in [('low', 30, .02), ('high', 70, .05)]:
                s[f'monthly_pmi_{label}'] = principal / 100000 * pmi_per_100k if down < .20 else 0.0
                insurance_cost = s[f'annual_insurance_bin_{label}']
                s[f'monthly_cost_proxy_{label}'] = s.monthly_pi_scenario + (s[f'annual_tax_{label}'] + insurance_cost) / 12 + s[f'monthly_pmi_{label}']
                # Closing-cost assumption already covers prepaids; do not add insurance twice.
                s[f'cash_to_close_{label}'] = s.price_2024 * (down + closing)
                for population, income in [('all', 'income'), ('renter', 'renter_income')]:
                    s[f'cost_ratio_{population}_{label}'] = s[f'monthly_cost_proxy_{label}'] * 12 / s[income]
                    s[f'cash_to_income_{population}_{label}'] = s[f'cash_to_close_{label}'] / s[income]
            rows.append(s)
    scenarios = pd.concat(rows, ignore_index=True)
    assert len(scenarios) == 6 * len(base)
    assert (scenarios.cash_to_close_low <= scenarios.cash_to_close_high).all()
    costs_valid = scenarios[['monthly_cost_proxy_low', 'monthly_cost_proxy_high']].notna().all(axis=1)
    assert (scenarios.loc[costs_valid, 'monthly_cost_proxy_low'] <= scenarios.loc[costs_valid, 'monthly_cost_proxy_high']).all()
    scenarios.to_csv(PROCESSED / 'entry_cost_scenarios.csv', index=False)
    summaries = []
    for (down, spread), group in scenarios.groupby(['down_payment_share', 'assumed_rate_spread']):
        for population, w in [('all', 'households'), ('renter', 'renter_households')]:
            valid = group[[f'cost_ratio_{population}_low', f'cost_ratio_{population}_high', w]].notna().all(axis=1) & (group[w] > 0)
            g = group[valid]
            lo, hi = g[f'cost_ratio_{population}_low'], g[f'cost_ratio_{population}_high']
            summaries.append({'down_payment_share': down, 'assumed_rate_spread': spread, 'income_population': population,
                              'n_counties': len(g), 'upper_cost_proxy_unbounded_counties': int(np.isinf(hi).sum()),
                              'households_in_included_counties': float(g[w].sum()),
                              'median_cost_proxy_ratio_low': lo.median(), 'median_cost_proxy_ratio_high': hi.median(),
                              'median_cash_income_low': g[f'cash_to_income_{population}_low'].median(),
                              'median_cash_income_high': g[f'cash_to_income_{population}_high'].median(),
                              'county_share_above_28pct_low': (lo > .28).mean(),
                              'county_share_above_28pct_high': (hi > .28).mean(),
                              'household_weighted_county_exposure_above_28pct_low': np.average(lo > .28, weights=g[w]),
                              'household_weighted_county_exposure_above_28pct_high': np.average(hi > .28, weights=g[w])})
    pd.DataFrame(summaries).to_csv(OUT / 'entry_cost_summary.csv', index=False)
    # Income-only MOE classification: costs and prices held fixed.
    m = frame.copy()
    annual_pi = .8 * m.price_2024 * payment_factor(.0703) * 12
    m['renter_pi_income_moe_low'] = annual_pi / (m.renter_income + m.renter_income_moe)
    m['renter_pi_income_moe_high'] = np.where(m.renter_income > m.renter_income_moe, annual_pi / (m.renter_income - m.renter_income_moe), np.inf)
    valid = (m.renter_income > 0) & m.renter_income_moe.notna()
    # Missing income/MOE is not evidence of an unbounded interval.
    m.loc[~valid, ['renter_pi_income_moe_low', 'renter_pi_income_moe_high']] = np.nan
    m['renter_pi_28pct_moe_status'] = np.select(
        [~valid, m.renter_pi_income_moe_low > .28, m.renter_pi_income_moe_high <= .28],
        ['missing_income_or_moe', 'above_across_income_moe_range', 'below_across_income_moe_range'], default='straddles_28pct')
    m.to_csv(OUT / 'renter_income_uncertainty.csv', index=False)
    con = duckdb.connect(str(PROCESSED / 'buyability.duckdb'))
    con.register('extended', scenarios)
    con.execute('CREATE OR REPLACE TABLE entry_cost_scenarios AS SELECT * FROM extended')
    con.close()
    map_data = scenarios[(scenarios.down_payment_share == .20) & (scenarios.assumed_rate_spread == 0)][
        ['geoid', 'NAME', 'cost_ratio_renter_low', 'cost_ratio_renter_high', 'cash_to_income_renter_low', 'cash_to_income_renter_high', 'tax_top_coded', 'insurance_open_upper_bin']].copy()
    map_data['cost_upper_unbounded'] = np.isinf(map_data.cost_ratio_renter_high)
    map_data['cost_ratio_renter_high'] = map_data.cost_ratio_renter_high.replace(np.inf, np.nan)
    history = pd.read_csv(PROCESSED / 'historical_decomposition_renter_income.csv', dtype={'geoid': str})
    map_data = map_data.merge(history[['geoid', 'change_pp']], on='geoid', how='left', validate='1:1')
    shapes = gpd.read_file(RAW / 'counties2024.zip').rename(columns={'GEOID': 'geoid'})
    shapes = shapes[shapes.STATEFP.astype(int) < 60][['geoid', 'STATEFP', 'geometry']]
    mapped = shapes.merge(map_data, on='geoid', how='left', validate='1:1').to_crs(4326)
    for flag in ['tax_top_coded', 'insurance_open_upper_bin', 'cost_upper_unbounded']:
        mapped[flag] = mapped[flag].astype('boolean')
    mapped.to_file(PROCESSED / 'extended_research_layers.geojson', driver='GeoJSON')
    return {'scenario_rows': len(scenarios), 'cost_summary': summaries,
            'insurance_missing_counties': int(frame.annual_insurance_bin_low.isna().sum()),
            'insurance_open_upper_bin_counties': int(frame.insurance_open_upper_bin.sum()),
            'tax_top_coded_counties': int(frame.tax_top_coded.sum()),
            'tax_bottom_coded_counties': int(frame.tax_bottom_coded.sum()),
            'renter_income_moe_classification': m.renter_pi_28pct_moe_status.value_counts().to_dict()}

def main():
    base = pd.read_csv(PROCESSED / 'buyability_scenarios.csv', dtype={'geoid': str, 'STATEFP': str})
    base = base[base.scenario == 'rate_7_03pct'].copy()
    base = base[['geoid', 'NAME', 'STATEFP', 'price_2024', 'income', 'income_moe', 'renter_income', 'renter_income_moe']]
    historical = historical_analysis(base)
    costs = cost_analysis(base)
    summary = {'historical': historical, 'costs': costs,
               'interpretation': 'Accounting decomposition and financing/cost-proxy scenarios, not causal effects or household qualification estimates.'}
    (OUT / 'extended_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    write_report(summary)
    print(json.dumps({'historical': historical, 'costs': {k:v for k,v in costs.items() if k != 'cost_summary'}}, indent=2))

def write_report(summary):
    historical = pd.DataFrame(summary['historical']['results'])
    historical['Population'] = historical.income_population.map({'income': 'All households', 'renter_income': 'Renter households'})
    historical['Counties'] = historical.n_counties
    for field, label in [('median_ratio_2019','2019 median P&I burden'), ('median_ratio_2024','2024 median P&I burden'), ('share_counties_increased','Counties with increased burden')]:
        historical[label] = historical[field].map(lambda v: f'{100*v:.1f}%')
    htable = historical[['Population', 'Counties', '2019 median P&I burden', '2024 median P&I burden', 'Counties with increased burden']].to_html(index=False, border=0)
    costs = pd.DataFrame(summary['costs']['cost_summary'])
    costs = costs[(costs.income_population == 'renter') & (costs.assumed_rate_spread == 0)].copy()
    costs['Down payment'] = costs.down_payment_share.map(lambda v:f'{100*v:.0f}%')
    costs['Median county monthly cost / renter income'] = costs.apply(lambda r:f'{100*r.median_cost_proxy_ratio_low:.1f}–{100*r.median_cost_proxy_ratio_high:.1f}%',axis=1)
    costs['Median county upfront cash / annual renter income'] = costs.apply(lambda r:f'{100*r.median_cash_income_low:.1f}–{100*r.median_cash_income_high:.1f}%',axis=1)
    ctable = costs[['Down payment', 'Median county monthly cost / renter income', 'Median county upfront cash / annual renter income']].to_html(index=False, border=0)
    cost_count = int(costs.iloc[0].n_counties)
    open_count = int(costs.iloc[0].upper_cost_proxy_unbounded_counties)
    status = summary['costs']['renter_income_moe_classification']
    exclusions = pd.read_csv(OUT/'historical_coverage_audit.csv').historical_exclusion.value_counts()
    rate_old, rate_new = [summary['historical']['rates'][str(y)] for y in [2019, 2024]]
    figure = base64.b64encode((OUT/'historical_decomposition.png').read_bytes()).decode()
    report = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Home buyability — research update</title><style>body{{font:17px/1.6 system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 22px;color:#172c38}}h1,h2{{line-height:1.2}}h2{{margin-top:36px}}table{{border-collapse:collapse;width:100%;font-size:15px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #ccd6da}}th{{background:#eef3f4}}img{{width:100%}}.note{{background:#f5f2e8;padding:16px}}a{{color:#126b85}}</style>
<h1>The geography of entry into homeownership</h1><p>Research update · October 2, 2026 · Reproducible descriptive results</p>
<p class="note">These results combine real public data with explicit financing scenarios. They do not estimate mortgage approval, households' liquid wealth, causal monetary-policy effects, or rental spillovers.</p>
<h2>Historical comparison</h2><p>2024 versus 2019 annual-average Zillow home values; non-overlapping 2020–2024 and 2015–2019 ACS income estimates in each endpoint year's dollars. Mortgage rates are the mean of 52 Freddie Mac weekly observations per year: {rate_old:.3f}% and {rate_new:.3f}%. All loans assume 20% down and 360 monthly payments.</p>{htable}
<p>The sample retains matched county GEOIDs with valid data and no more than 1% relative symmetric-difference area between 2019 and 2024 cartographic boundaries. This is a comparability screen, not full boundary harmonization. It excludes {exclusions.get('incomplete_2019_ZHVI',0)} baseline counties for incomplete 2019 prices and {exclusions.get('boundary_difference_above_1pct',0)} for larger geometry differences. Connecticut was already excluded from the baseline because Zillow and Census geographies differ.</p>
<img alt="Mean arithmetic contributions of prices, income and rates to changes in county payment burden" src="data:image/png;base64,{figure}">
<p>Shapley contributions average across all six possible orders of updating price, nominal income and rate. Contributions sum to the change within every county. Means of contributions add to the mean change; medians need not add. Inflation is not separately identified, and nominal income growth is not necessarily real purchasing-power growth.</p>
<h2>Upfront cash and recurring cost scenarios</h2>{ctable}
<p>Each row uses the same {cost_count:,} counties with valid renter income and cost inputs. Home values and income remain fixed at the baseline vintage; 7.03% is a scenario rate. Monthly costs add existing mortgaged owners' median property-tax proxy, a grouped-data insurance-median interval, and PMI at $30–$70 monthly per $100,000 borrowed for down payments below 20%. Upfront cash is down payment plus assumed closing costs of 2–5% of value; reserves and assistance are not modeled. The model also exports a separate +0.50 percentage-point rate sensitivity.</p>
<p class="note">Ranges are assumption/data-censoring ranges, not confidence intervals or market quotes. Summing separate county medians does not produce an observed median household bill. Existing-owner taxes can differ from a buyer's reassessed taxes; existing-owner insurance may differ from a new quote. HOA fees, maintenance, utilities and other debts are excluded. An open-ended tax or insurance category remains unbounded, rather than being assigned an invented maximum. {open_count} renter-sample counties have unbounded upper cost proxies.</p>
<h2>Income uncertainty</h2><p>At the original 7.03%, 20%-down P&I scenario, {status.get('above_across_income_moe_range',0):,} counties remain above the 28% benchmark throughout the renter-income margin-of-error range, {status.get('below_across_income_moe_range',0):,} remain below, {status.get('straddles_28pct',0):,} straddle it, and {status.get('missing_income_or_moe',0):,} lack usable renter-income inputs. This sensitivity holds prices fixed and does not incorporate tax, insurance or price uncertainty.</p>
<h2>Interpretation and remaining work</h2><p>The results support a descriptive paper about entrant-focused payment burdens and capital requirements. They do not yet support the original abstract's assertions about metro-core divergence, rental spillovers, supply constraints or causal inflation transmission. Geographic coverage, PMMS's 2022 methodology change, its conforming-loan population, and income period estimates must remain explicit limitations.</p>
<p>The analysis exports GeoJSON for external inspection. Metropolitan comparisons, purchaser-specific tax reassessment and insurance estimates, and user evaluation remain outside the completed analysis.</p>
<h2>Primary sources</h2><ul>
<li><a href="https://www.zillow.com/research/data/">Zillow Research housing data</a></li>
<li><a href="https://www2.census.gov/programs-surveys/acs/summary_file/2019/data/">2019 ACS official bulk files</a> and <a href="https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/">2024 ACS official bulk files</a></li>
<li><a href="https://api.census.gov/data/2024/acs/acs5/groups/B25141.html">Insurance cost bins: B25141</a>; <a href="https://api.census.gov/data/2024/acs/acs5/groups/B25103.html">property taxes: B25103</a></li>
<li><a href="https://www.freddiemac.com/pmms/docs/historicalweeklydata.xlsx">Freddie Mac historical weekly rates</a>; <a href="https://www.freddiemac.com/research/insight/20221103-freddie-macs-newly-enhanced-mortgage-rate-survey">2022 methodology change</a></li>
<li><a href="https://myhome.freddiemac.com/buying/breaking-down-pmi">PMI scenario range</a>; <a href="https://myhome.freddiemac.com/blog/homebuying/what-are-closing-costs-and-how-much-will-i-pay">closing-cost scenario range</a></li></ul>
<p>Exact file URLs and SHA-256 hashes are in data/raw/manifest.json. Calculations: scripts/extend_analysis.py. Tables: outputs/*summary.csv. GeoJSON: data/processed/extended_research_layers.geojson.</p></html>'''
    (OUT/'research_update.html').write_text(report)

if __name__ == '__main__':
    main()
