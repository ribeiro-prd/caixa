from pathlib import Path
import subprocess
import sys
root = Path.cwd()
if not (root / 'src' / 'caixa_joias' / 'cli.py').exists():
    raise SystemExit('Run from repo root. Missing src/caixa_joias/cli.py')
subprocess.run([sys.executable, 'src/caixa_joias/cli_patch_warehouse.py'], check=True)
print('Installed strategy package.')
