"""Download public source files with curl; retain checksums and retrieval times."""
import hashlib
import json
from pathlib import Path
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
BASE = 'https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/'
SOURCES = {
    'zhvi_county.csv': 'https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv',
    'acs2024_b19013.dat': BASE + 'acsdt5y2024-b19013.dat',
    'acs2024_b25119.dat': BASE + 'acsdt5y2024-b25119.dat',
    'counties2024.zip': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip',
}

STATES = '''AL Alabama;AK Alaska;AZ Arizona;AR Arkansas;CA California;CO Colorado;CT Connecticut;DE Delaware;DC DistrictOfColumbia;FL Florida;GA Georgia;HI Hawaii;ID Idaho;IL Illinois;IN Indiana;IA Iowa;KS Kansas;KY Kentucky;LA Louisiana;ME Maine;MD Maryland;MA Massachusetts;MI Michigan;MN Minnesota;MS Mississippi;MO Missouri;MT Montana;NE Nebraska;NV Nevada;NH NewHampshire;NJ NewJersey;NM NewMexico;NY NewYork;NC NorthCarolina;ND NorthDakota;OH Ohio;OK Oklahoma;OR Oregon;PA Pennsylvania;RI RhodeIsland;SC SouthCarolina;SD SouthDakota;TN Tennessee;TX Texas;UT Utah;VT Vermont;VA Virginia;WA Washington;WV WestVirginia;WI Wisconsin;WY Wyoming'''

def extended_sources():
    sources = {f'acs2024_{t}.dat': BASE + f'acsdt5y2024-{t}.dat' for t in ['b25003', 'b25103', 'b25141']}
    sources['pmms_historical.xlsx'] = 'https://www.freddiemac.com/pmms/docs/historicalweeklydata.xlsx'
    sources['acs2019_templates.zip'] = 'https://www2.census.gov/programs-surveys/acs/summary_file/2019/data/2019_5yr_Summary_FileTemplates.zip'
    sources['counties2019.zip'] = 'https://www2.census.gov/geo/tiger/GENZ2019/shp/cb_2019_us_county_500k.zip'
    for state in STATES.split(';'):
        abbr, name = state.split()
        base = f'https://www2.census.gov/programs-surveys/acs/summary_file/2019/data/5_year_seq_by_state/{name}/All_Geographies_Not_Tracts_Block_Groups/'
        for filename in [f'g20195{abbr.lower()}.csv', f'20195{abbr.lower()}0058000.zip', f'20195{abbr.lower()}0117000.zip']:
            sources[f'acs2019/{filename}'] = base + filename + ('?download=1' if filename.endswith('.csv') else '')
    return sources

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extended', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW / 'manifest.json'
    prior = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = dict(prior)
    sources = dict(SOURCES)
    if args.extended:
        sources.update(extended_sources())
    def fetch(item):
        name, url = item
        path = RAW / name
        path.parent.mkdir(parents=True, exist_ok=True)
        expected = b'PK' if name.endswith(('.zip', '.xlsx')) else b'GEO_ID|' if name.endswith('.dat') else b'ACSSF' if name.startswith('acs2019/') else b'RegionID,'
        if not path.exists() or not path.read_bytes().startswith(expected):
            temp = path.with_suffix(path.suffix + '.partial')
            subprocess.run(['curl', '-LsSf', '--retry', '2', '--max-time', '120', url, '-o', str(temp)], check=True)
            if not temp.read_bytes().startswith(expected):
                raise ValueError(f'{name}: unexpected download payload; not promoted to raw data')
            temp.replace(path)
        payload = path.read_bytes()
        if not payload.startswith(expected):
            raise ValueError(f'{name}: unexpected payload (possibly an HTML error)')
        digest = hashlib.sha256(payload).hexdigest()
        previous = prior.get(name, {})
        if previous.get('sha256') and previous['sha256'] != digest:
            raise ValueError(f'{name}: checksum differs from the recorded research vintage; preserve the prior manifest and investigate before updating data')
        return name, {
            'url': url, 'sha256': digest, 'bytes': len(payload),
            'local_file_timestamp_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            'first_manifest_recorded_utc': previous.get('first_manifest_recorded_utc', datetime.now(timezone.utc).isoformat()),
            'note': 'Cached files are reused. Local timestamp is not a provider release date.'
        }
    # Modest concurrency for independent public-file downloads, never analysis joins.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name, entry in pool.map(fetch, sources.items()):
            manifest[name] = entry
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Validated and recorded', len(manifest), 'public source files')

if __name__ == '__main__':
    main()
