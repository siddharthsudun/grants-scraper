import json, sys
sys.stdout.reconfigure(line_buffering=True)

from enrich import enrich_grants
from utils import deduplicate_grants, save_to_csv
from pathlib import Path
from datetime import datetime

data = json.load(open('output/raw_20260430_152734.json'))
print(f'Enriching {len(data)} pages with Ollama llama3.1:8b...')

grants = enrich_grants(data)
print(f'\n{len(grants)} raw grants extracted')

grants = deduplicate_grants(grants)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_path = Path(f'output/grants_{ts}.csv')
save_to_csv(grants, csv_path)

top = sorted(grants, key=lambda x: x.get('relevance_score', 0), reverse=True)[:20]
print(f'\nTotal unique grants: {len(grants)}')
print(f'  {"#":<3} {"Score":<6} {"Type":<14} {"Amount":<22} Name')
print(f'  {"-"*80}')
for i, g in enumerate(top, 1):
    print(f'  {i:<3} {str(g.get("relevance_score","?")):<6} {str(g.get("type","?"))[:13]:<14} {str(g.get("amount","TBD"))[:21]:<22} {g.get("name","?")[:55]}')
print(f'\nCSV: {csv_path}')
