from pathlib import Path

ROOT = Path.cwd()
cli = ROOT / "src" / "caixa_joias" / "cli.py"

if not cli.exists():
    raise SystemExit("Run this from repo root. Missing src/caixa_joias/cli.py")

text = cli.read_text(encoding="utf-8")

imp = "from caixa_joias.warehouse.build import build_warehouse\n"
if imp not in text:
    text = text.replace("import pandas as pd\n", "import pandas as pd\n" + imp)

cmd = """

@app.command("build-warehouse")
def build_warehouse_command(
    processed_dir: Path = typer.Option(Path("data/processed"), "--processed-dir"),
    raw_dir: Path = typer.Option(Path("data/raw/caixa"), "--raw-dir"),
    out_db: Path = typer.Option(Path("data/warehouse/caixa_joias.duckdb"), "--out-db"),
    out_exports_dir: Path = typer.Option(Path("data/exports/warehouse"), "--out-exports-dir"),
) -> None:
    build_warehouse(
        processed_dir=processed_dir,
        raw_dir=raw_dir,
        out_db=out_db,
        out_exports_dir=out_exports_dir,
    )


@app.command("serve")
def serve_command(
    app_path: Path = typer.Option(Path("src/caixa_joias/dashboard/app.py"), "--app-path"),
) -> None:
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)
"""

if '@app.command("build-warehouse")' not in text:
    text = text.rstrip() + cmd + "\n"

cli.write_text(text, encoding="utf-8")
print("CLI ready: build-warehouse and serve")
