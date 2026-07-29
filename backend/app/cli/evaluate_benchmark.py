"""CLI: evaluate the research retrieval benchmark against Chroma.

Example:

  cd backend
  CHROMA_HOST=localhost CHROMA_PORT=8001 \\
  EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu \\
  python -m app.cli.evaluate_benchmark --top-k 5 --save-json --save-markdown
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "scripts" / "dataset" / "benchmark"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_benchmark import main as evaluate_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    # Preserve argparse surface expected by the research pipeline docs.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", default=None)
    parser.add_argument("--benchmark", default=None)
    parser.add_argument("--collection", default="devguard_research_knowledge")
    parser.add_argument("--save-json", action="store_true")
    parser.add_argument("--save-markdown", action="store_true")
    parser.add_argument("--save-charts", action="store_true")
    parser.add_argument(
        "--labels",
        choices=("gold", "candidates"),
        default="gold",
    )
    # Re-parse with the shared evaluator for full help / validation.
    return evaluate_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
