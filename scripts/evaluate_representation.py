"""Compare alternative representations on common samples; export an offline explorer."""
import json
import math
import platform
import time
import numpy as np
import pandas as pd
import geopandas as gpd
from build_baseline import ROOT, plt

OUT = ROOT / 'outputs'
DATA = ROOT / 'data/processed'

def evaluate():
    started = time.perf_counter()
    baseline = pd.read_csv(DATA/'buyability_scenarios.csv', dtype={'geoid':str,'STATEFP':str})
    baseline = baseline[baseline.scenario == 'rate_7_03pct'][['geoid','NAME','pti_all','pti_renter']]
    costs = pd.read_csv(DATA/'entry_cost_scenarios.csv', dtype={'geoid':str})
    costs = costs[(costs.down_payment_share == .2)&(costs.assumed_rate_spread == 0)]
    x = baseline.merge(costs[['geoid','cost_ratio_renter_low','cost_ratio_renter_high']],on='geoid',validate='1:1')
    pairs = [('Income population','pti_all','pti_renter'), ('Add local cost proxies (lower bound)','pti_renter','cost_ratio_renter_low'), ('Combined change (lower bound)','pti_all','cost_ratio_renter_low')]
    metrics, transitions = [], []
    for label,a,b in pairs:
        sample = x[np.isfinite(x[a])&np.isfinite(x[b])].copy()
        n = len(sample)
        k = math.ceil(n*.1)
        # GEOID breaks ties reproducibly for set overlap; Spearman uses average ranks.
        top_a=set(sample.sort_values([a,'geoid'],ascending=[False,True]).head(k).geoid)
        top_b=set(sample.sort_values([b,'geoid'],ascending=[False,True]).head(k).geoid)
        rho=sample[a].rank().corr(sample[b].rank())
        metrics.append({'comparison':label,'n_counties':n,'spearman_rank_correlation':rho,
                        'top_decile_size':k,'top_decile_retained':len(top_a&top_b),
                        'top_decile_overlap_fraction':len(top_a&top_b)/k,
                        'median_difference_pp':100*(sample[b]-sample[a]).median()})
        for threshold in [.25,.28,.30,.36]:
            initial=sample[a]>threshold; final=sample[b]>threshold
            transitions.append({'comparison':label,'threshold':threshold,'n_counties':n,
                                'both_below_or_equal':int((~initial&~final).sum()),
                                'below_to_above':int((~initial&final).sum()),
                                'above_to_below':int((initial&~final).sum()),
                                'both_above':int((initial&final).sum())})
        sample['rank_before']=sample[a].rank(ascending=False)
        sample['rank_after']=sample[b].rank(ascending=False)
        sample['rank_change']=sample.rank_after-sample.rank_before
        sample.to_csv(OUT/f'representation_counties_{a}_to_{b}.csv',index=False)
    metrics=pd.DataFrame(metrics); transitions=pd.DataFrame(transitions)
    assert (transitions[['both_below_or_equal','below_to_above','above_to_below','both_above']].sum(axis=1)==transitions.n_counties).all()
    assert metrics.spearman_rank_correlation.between(-1,1).all()
    metrics.to_csv(OUT/'representation_comparison.csv',index=False)
    transitions.to_csv(OUT/'representation_transitions.csv',index=False)
    paired=x.dropna(subset=['pti_all','pti_renter','cost_ratio_renter_low'])
    fig,axes=plt.subplots(1,2,figsize=(11,5),sharex=True,sharey=True)
    for ax,col,title in zip(axes,['pti_renter','cost_ratio_renter_low'],['Renter income; P&I only','Renter income + local cost proxies\nLower bound of cost scenario']):
        ax.scatter(paired.pti_all*100,paired[col]*100,s=7,alpha=.35,color='#176c76')
        limit=150
        ax.plot([0,limit],[0,limit],color='#888',linewidth=1)
        ax.axhline(28,color='#b35430',linestyle='--',linewidth=1)
        ax.axvline(28,color='#b35430',linestyle='--',linewidth=1)
        ax.set(xlim=(0,limit),ylim=(0,limit),xlabel='Original all-household P&I burden (%)',ylabel='Comparison burden (%)',title=title)
    clipped=int(((paired.pti_all>1.5)|(paired.pti_renter>1.5)|(paired.cost_ratio_renter_low>1.5)).sum())
    fig.suptitle(f'Representation changes the comparison · {len(paired):,} common counties')
    fig.text(.05,.015,f'7.03% rate, 20% down, fixed 2024 inputs. Dashed lines: 28% benchmark. {clipped} counties outside plot bounds; retained in statistics.',fontsize=9)
    fig.tight_layout(rect=(0,.045,1,.94))
    fig.savefig(OUT/'representation_comparison.png',dpi=180)
    fig.savefig(OUT/'representation_comparison.pdf')
    plt.close(fig)
    result={'comparisons':metrics.to_dict(orient='records'),'threshold_28pct':transitions[transitions.threshold==.28].to_dict(orient='records'),
            'interpretation':'Changes in representation, not improvements in predictive accuracy or measured user comprehension.',
            'elapsed_seconds_including_figure_exports':time.perf_counter()-started,
            'platform':platform.platform(),'python':platform.python_version()}
    (OUT/'representation_evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def svg_paths(shapes):
    lower=shapes[~shapes.STATEFP.isin(['02','15'])].to_crs(5070)
    xmin,ymin,xmax,ymax=lower.total_bounds
    scale=min(970/(xmax-xmin),590/(ymax-ymin))
    paths=[]
    for row in lower.itertuples():
        geom=row.geometry.simplify(2000,preserve_topology=True)
        parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
        commands=[]
        for poly in parts:
            for ring in [poly.exterior,*poly.interiors]:
                xy=[(15+(a-xmin)*scale,15+(ymax-b)*scale) for a,b in ring.coords]
                commands.append('M'+'L'.join(f'{a:.1f},{b:.1f}' for a,b in xy)+'Z')
        paths.append(f'<path data-id="{row.geoid}" d="{"".join(commands)}" fill-rule="evenodd"/>')
    return ''.join(paths)

def build_explorer():
    facts=pd.read_csv(DATA/'observed_cost_proxies.csv',dtype={'geoid':str,'STATEFP':str})
    shapes=gpd.read_file(ROOT/'data/raw/counties2024.zip').rename(columns={'GEOID':'geoid'})
    shapes=shapes[shapes.STATEFP.astype(int)<60]
    table=shapes[['geoid','NAME','STATEFP']].merge(facts.drop(columns=['NAME','STATEFP']),on='geoid',how='left',validate='1:1')
    hist=pd.read_csv(DATA/'historical_decomposition_renter_income.csv',dtype={'geoid':str})
    table=table.merge(hist[['geoid','ratio_2019','ratio_2024','change_pp']],on='geoid',how='left',validate='1:1')
    table['upper_cost_unbounded']=np.isinf(table.annual_tax_high)|np.isinf(table.annual_insurance_bin_high)
    # Serialize infinities as null and carry explicit flags so they are not conflated with missing data.
    payload=table.replace([np.inf,-np.inf],np.nan).to_json(orient='records',double_precision=15)
    paths=svg_paths(shapes)
    template=(ROOT/'visualization/explorer.html').read_text()
    result=template.replace('__DATA__',payload).replace('__MAP_PATHS__',paths)
    (OUT/'buyability_explorer.html').write_text(result)
    assert len(json.loads(payload))==3144
    print('Offline explorer:',OUT/'buyability_explorer.html')

if __name__=='__main__':
    print(json.dumps(evaluate(),indent=2))
    build_explorer()
