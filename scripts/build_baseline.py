"""Real-data descriptive pilot. No causal estimates or synthetic observations."""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42  # Embed TrueType fonts in exported figures.
import matplotlib.pyplot as plt

def acs(table, columns):
    frame = pd.read_csv(ROOT / f'data/raw/acs2024_{table.lower()}.dat', sep='|', dtype=str)
    frame = frame[frame.GEO_ID.str.fullmatch(r'0500000US\d{5}')].copy()
    frame['geoid'] = frame.GEO_ID.str[-5:]
    frame = frame[['geoid', *columns]].rename(columns=columns)
    for col in columns.values():
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
        # ACS special values, missing estimates and zero incomes cannot be divisors.
        frame.loc[frame[col] < 0, col] = np.nan
    assert not frame.geoid.duplicated().any()
    return frame

def main():
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    processed = ROOT / 'data/processed'
    processed.mkdir(exist_ok=True)
    income = acs('B19013', {'B19013_E001': 'income', 'B19013_M001': 'income_moe'})
    renter = acs('B25119', {'B25119_E003': 'renter_income', 'B25119_M003': 'renter_income_moe'})
    values = pd.read_csv(ROOT / 'data/raw/zhvi_county.csv', dtype={'StateCodeFIPS': str, 'MunicipalCodeFIPS': str},
                         usecols=lambda c: c.startswith('2024-') or c in ['StateCodeFIPS', 'MunicipalCodeFIPS', 'State', 'Metro', 'RegionName'])
    values['geoid'] = values.StateCodeFIPS.str.zfill(2) + values.MunicipalCodeFIPS.str.zfill(3)
    assert not values.geoid.duplicated().any()
    months = [c for c in values if c.startswith('2024-')]
    assert len(months) == 12, 'Require all twelve 2024 months in the source schema'
    values['price_months'] = values[months].notna().sum(axis=1)
    values['price_2024'] = values[months].mean(axis=1).where(values.price_months == 12)
    counties = gpd.read_file(ROOT / 'data/raw/counties2024.zip').rename(columns={'GEOID': 'geoid'})
    counties = counties[counties.STATEFP.astype(int) < 60].copy()  # 50 states and DC
    assert not counties.geoid.duplicated().any()
    frame = counties[['geoid', 'NAME', 'STATEFP']].merge(income, on='geoid', how='left', validate='1:1').merge(renter, on='geoid', how='left', validate='1:1')
    frame = frame.merge(values[['geoid', 'State', 'Metro', 'price_2024', 'price_months']], on='geoid', how='left', validate='1:1')
    frame['included'] = (frame.income > 0) & (frame.price_2024 > 0)
    frame['exclusion_reason'] = np.select([frame.price_2024.isna(), ~(frame.income > 0)], ['missing_or_incomplete_2024_ZHVI', 'missing_or_invalid_income'], default='included')
    frame.to_csv(out / 'county_coverage_audit.csv', index=False)
    unmatched = values[~values.geoid.isin(counties.geoid)]
    unmatched[['geoid', 'RegionName', 'State']].to_csv(out / 'zillow_unmatched_geographies.csv', index=False)
    eligible = frame[frame.included].copy()
    eligible.loc[~(eligible.renter_income > 0), 'renter_income'] = np.nan
    scenarios = pd.DataFrame({'scenario': ['rate_3pct', 'rate_6pct', 'rate_7_03pct'], 'annual_rate': [0.03, 0.06, 0.0703]})
    con = duckdb.connect(str(processed / 'buyability.duckdb'))
    con.register('eligible', eligible)
    con.register('scenarios', scenarios)
    con.execute((ROOT / 'sql/buyability.sql').read_text())
    result = con.sql('SELECT * FROM buyability ORDER BY geoid, annual_rate').df()
    result.to_csv(processed / 'buyability_scenarios.csv', index=False)
    # Independent recurrence checks amortization, rather than restating the SQL formula.
    sample = result.iloc[0]
    balance = sample.principal
    for _ in range(360):
        balance = balance * (1 + sample.annual_rate / 12) - sample.monthly_pi
    assert abs(balance) < 0.01
    pivot = result.pivot(index='geoid', columns='scenario', values='pti_all')
    multiplier = pivot.rate_7_03pct / pivot.rate_3pct
    assert multiplier.max() - multiplier.min() < 1e-10
    assert (pivot.rate_7_03pct > pivot.rate_6pct).all()
    assert len(result) == 3 * len(eligible)
    rows = []
    for scenario, group in result.groupby('scenario'):
        for income_type in ['all', 'renter']:
            series = group[f'pti_{income_type}'].dropna()
            row = {'scenario': scenario, 'income_type': income_type, 'n_counties': len(series), 'median_pi_ratio': series.median()}
            for threshold in [0.25, 0.28, 0.30, 0.36]:
                row[f'share_counties_pi_above_{int(threshold*100)}pct'] = (series > threshold).mean()
            rows.append(row)
    pd.DataFrame(rows).to_csv(out / 'scenario_summary.csv', index=False)
    high = result[result.scenario == 'rate_7_03pct'].copy()
    high = high.merge(pivot[['rate_3pct']], on='geoid', validate='1:1')
    high['delta_pi_percentage_points'] = 100 * (high.pti_all - high.rate_3pct)
    geo = counties[['geoid', 'STATEFP', 'geometry']].merge(high.drop(columns='STATEFP'), on='geoid', how='left', validate='1:1').to_crs(4326)
    geo.to_file(processed / 'buyability_2024_rate_scenario.geojson', driver='GeoJSON')
    # County weights are equal; this does not estimate a share of households.
    summary = {
        'status': 'DESCRIPTIVE PILOT; not a 2026 affordability estimate',
        'price_period': 'mean of 12 monthly ZHVI observations in 2024',
        'income_period': '2020-2024 ACS five-year estimate, 2024 dollars',
        'county_universe_50_states_dc': len(counties), 'included_counties': len(eligible),
        'excluded_counties': int((~frame.included).sum()),
        'zillow_geographies_outside_boundary_universe': len(unmatched),
        'payment_multiplier_7_03_vs_3': float(multiplier.median()),
        'checks': ['unique GEOIDs', 'one-to-one joins', '12 price months', 'loan balance amortizes to zero', 'rate monotonicity', 'uniform rate multiplier', 'three scenarios per eligible county'],
        'limitations': ['P&I excludes tax, insurance, HOA, maintenance', '20% down assumed; no observed liquid wealth', 'ACS period estimates are not point-in-time incomes', 'No household eligibility or rental-spillover inference', 'Income MOE bounds omit home-value uncertainty and are not joint confidence intervals'],
    }
    (out / 'baseline_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    lower48 = geo[~geo.STATEFP.isin(['02', '15'])].to_crs(5070)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, col, title in zip(axes, ['pti_all', 'pti_renter'], ['All-household median income', 'Renter-household median income']):
        lower48.plot(column=col, ax=ax, cmap='YlOrRd', vmin=0, vmax=1, legend=True,
                     missing_kwds={'color': '#dddddd'}, legend_kwds={'label': 'P&I / monthly income (scale capped at 1)'})
        ax.set_title(title)
        ax.set_axis_off()
    fig.suptitle('2024 county payment burden under a 7.03% mortgage-rate scenario', fontsize=15)
    fig.text(.05, .03, '2024 mean ZHVI; 2020–2024 ACS income; 30-year term; 20% down. P&I only. Gray = missing.\nDescriptive scenario, not observed 2026 affordability. Alaska and Hawaii omitted from figure only.', fontsize=10)
    fig.savefig(out / 'payment_burden_pilot.png', dpi=180, bbox_inches='tight')
    fig.savefig(out / 'payment_burden_pilot.pdf', bbox_inches='tight')
    plt.close(fig)
    print(json.dumps(summary, indent=2))
    print(pd.DataFrame(rows).to_string(index=False))

if __name__ == '__main__':
    main()
