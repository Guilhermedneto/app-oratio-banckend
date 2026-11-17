"""Gera o OpenAPI para o front: python -m app.export_openapi <arquivo>"""

import json
import sys

from app.main import app


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
