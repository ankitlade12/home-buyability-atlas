"""Audit cached-source integrity, analytical invariants, coverage and common samples.

Run after build_baseline.py, extend_analysis.py and evaluate_representation.py.
Assertions establish consistency, not external validity or causal identification.
"""
import hashlib
import json
import platform
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from build_baseline import ROOT, acs

def main():
    raw, data, out = ROOT/'data/raw', ROOT/'data/processed', ROOT/'outputs'
    manifest = json.loads((raw/'manifest.json').read_text())
    frozen = json.loads((ROOT/'provenance/source_manifest.json').read_text())
    assert set(frozen) == set(manifest), 'Source set differs from frozen research vintage'
    assert all(frozen[k]['sha256'] == manifest[k]['sha256'] for k in frozen), 'Source vintage changed'
    for name, metadata in manifest.items():
        path = raw/name
        assert path.stat().st_size == metadata['bytes'], name
        with path.open('rb') as handle:
            assert hashlib.file_digest(handle, 'sha256').hexdigest() == metadata['sha256'], name
    baseline = pd.read_csv(data/'buyability_scenarios.csv', dtype={'geoid':str})
    costs = pd.read_csv(data/'entry_cost_scenarios.csv', dtype={'geoid':str})
    assert not baseline.duplicated(['geoid','scenario']).any()
    assert not costs.duplicated(['geoid','down_payment_share','assumed_rate_spread']).any()
    assert costs.groupby('geoid').size().eq(6).all()
    # Reconcile SQL P&I with extended calculation at exactly matching terms.
    current = baseline[baseline.scenario.eq('rate_7_03pct')]
    selected = costs[costs.down_payment_share.eq(.2)&costs.assumed_rate_spread.eq(0)]
    common = current[['geoid','pti_all','pti_renter','monthly_pi']].merge(selected, on='geoid',validate='1:1')
    assert np.allclose(common.monthly_pi, common.monthly_pi_scenario, rtol=1e-12)
    complete = common.dropna(subset=['pti_all','pti_renter','cost_ratio_renter_low']).copy()
    rows=[]
    for threshold in [.25,.28,.30,.36]:
        a,b,c=[complete[k].gt(threshold) for k in ['pti_all','pti_renter','cost_ratio_renter_low']]
        rows.append({'threshold':threshold,'n_counties':len(complete),
                     'income_up':int((~a&b).sum()),'income_down':int((a&~b).sum()),
                     'cost_up':int((~b&c).sum()),'cost_down':int((b&~c).sum()),
                     'combined_up':int((~a&c).sum()),'combined_down':int((a&~c).sum())})
    pd.DataFrame(rows).to_csv(out/'audit_common_sample_transitions.csv',index=False)
    # Positive cost additions cannot lower burden. Income effects need not share that sign.
    assert (complete.cost_ratio_renter_low >= complete.pti_renter-1e-12).all()
    pivot=baseline.pivot(index='geoid',columns='scenario',values='pti_all')
    assert pivot.rate_3pct.rank().equals(pivot.rate_7_03pct.rank())
    geometry=json.loads((data/'extended_research_layers.geojson').read_text())
    flags={}
    for key in ['tax_top_coded','insurance_open_upper_bin','cost_upper_unbounded']:
        values=[feature['properties'].get(key) for feature in geometry['features']]
        assert all(value is None or isinstance(value,bool) for value in values),key
        flags[key]=sum(value is True for value in values)
    assert flags['cost_upper_unbounded']==int(np.isinf(selected.cost_ratio_renter_high).sum())
    uncertainty=pd.read_csv(out/'renter_income_uncertainty.csv')
    missing=uncertainty.renter_pi_28pct_moe_status.eq('missing_income_or_moe')
    assert uncertainty.loc[missing,['renter_pi_income_moe_low','renter_pi_income_moe_high']].isna().all().all()
    for population in ['income','renter_income']:
        history=pd.read_csv(data/f'historical_decomposition_{population}.csv')
        assert np.allclose(history[['price_contribution_pp','income_contribution_pp','rate_contribution_pp']].sum(axis=1),history.change_pp,atol=1e-10)
    coverage=pd.read_csv(out/'county_coverage_audit.csv',dtype={'geoid':str,'STATEFP':str})
    counts=acs('B25003',{'B25003_E001':'households','B25003_E003':'renter_households'})
    coverage=coverage.merge(counts,on='geoid',how='left',validate='1:1')
    coverage['complete_representation_sample']=coverage.geoid.isin(complete.geoid)
    coverage['historical_renter_sample']=coverage.geoid.isin(pd.read_csv(data/'historical_decomposition_renter_income.csv',dtype={'geoid':str}).geoid)
    assert coverage.households.notna().all() and coverage.renter_households.notna().all()
    coverage_rows=[]
    for sample in ['included','complete_representation_sample','historical_renter_sample']:
        mask=coverage[sample]
        coverage_rows.append({'sample':sample,'included_counties':int(mask.sum()),'excluded_counties':int((~mask).sum()),
            **{f'{weight}_coverage_share':float(coverage.loc[mask,weight].sum()/coverage[weight].sum()) for weight in ['households','renter_households']},
            'median_income_included':float(coverage.loc[mask,'income'].median()),
            'median_income_excluded':float(coverage.loc[~mask,'income'].median())})
    pd.DataFrame(coverage_rows).to_csv(out/'audit_population_coverage.csv',index=False)
    coverage.groupby('STATEFP').agg(counties=('geoid','size'),baseline_included=('included','sum'),complete_included=('complete_representation_sample','sum'),historical_renter_included=('historical_renter_sample','sum')).to_csv(out/'audit_state_coverage.csv')
    results={'audited_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
             'source_files_hash_verified':len(manifest),'scenario_rows':len(costs),
             'common_sample_counties':len(complete),'geojson_boolean_true_counts':flags,
             'common_sample_transitions':rows,'coverage':coverage_rows,
             'interpretation':'Internal consistency and coverage audit; not independent validation of household buyability.'}
    (out/'research_audit.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    main()
