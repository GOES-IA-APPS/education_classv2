from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.scripts.import_runner import run_import_all_cli


if __name__ == "__main__":
    raise SystemExit(run_import_all_cli())
