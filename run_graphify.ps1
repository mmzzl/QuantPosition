# Step 3A - AST Extraction
$python = Get-Content .graphify_python -Raw

& $python -c @"
import json
from graphify.extract import collect_files, extract
from pathlib import Path

code_files = []
with open('.graphify_detect.json', 'r', encoding='utf-8-sig') as f:
    detect = json.load(f)
for f in detect.get('files', {}).get('code', []):
    code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])

if code_files:
    result = extract(code_files)
    with open('.graphify_ast.json', 'w', encoding='utf-8') as out:
        json.dump(result, out, indent=2)
    print('AST: ' + str(len(result['nodes'])) + ' nodes, ' + str(len(result['edges'])) + ' edges')
else:
    with open('.graphify_ast.json', 'w', encoding='utf-8') as out:
        json.dump({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}, out)
    print('No code files - skipping AST extraction')
"@