"""Export the warehouse to static JSON the dashboard can read with no backend.

The dashboard normally talks to the FastAPI service over ``/api``. For a free,
server-less production deploy we bake the exact same responses into JSON files
under ``web/public/api-static/`` and let the browser read them directly (see
``web/src/lib/api.ts`` static mode). Because we drive the responses through the
real FastAPI app via ``TestClient``, the JSON shapes match the Pydantic schemas
byte-for-byte (dates, ``Page`` envelopes, etc.).

Run:  uv run python scripts/export_static_data.py
      (regenerated weekly by .github/workflows/pipeline.yml after run-all)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api.main import app

OUT = Path(__file__).resolve().parents[1] / "web" / "public" / "api-static"


def _write_json(rel: str, data: Any) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"  {rel}")


def _write_bytes(rel: str, data: bytes) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"  {rel}  ({len(data)} bytes)")


def _get(client: TestClient, path: str) -> Any:
    res = client.get(path)
    res.raise_for_status()
    return res.json()


def _collect_all(client: TestClient, path: str) -> list[dict]:
    """Page through a Page[T] endpoint and return every item."""
    items: list[dict] = []
    offset, limit = 0, 200
    while True:
        sep = "&" if "?" in path else "?"
        page = _get(client, f"{path}{sep}limit={limit}&offset={offset}")
        items.extend(page["items"])
        offset += limit
        if offset >= page["total"] or not page["items"]:
            break
    return items


def main() -> None:
    print(f"Exporting static API snapshot -> {OUT}")
    if OUT.exists():
        # Clear stale files (keeps deletes honest) but keep the dir.
        for p in sorted(OUT.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()

    with TestClient(app) as client:
        # Overview + feeds (full, unpaginated; the client filters/paginates).
        _write_json("overview.json", _get(client, "/stats/overview"))
        _write_json("signals.json", _collect_all(client, "/signals"))
        _write_json("changes.json", _collect_all(client, "/changes"))

        # Competitors + per-competitor analytics.
        competitors = _get(client, "/competitors")
        _write_json("competitors.json", competitors)
        for c in competitors:
            cid = c["id"]
            _write_json(f"competitors/{cid}.json", _get(client, f"/competitors/{cid}"))
            _write_json(
                f"competitors/{cid}/pricing-history.json",
                _get(client, f"/competitors/{cid}/pricing-history"),
            )
            _write_json(
                f"competitors/{cid}/hiring.json", _get(client, f"/competitors/{cid}/hiring")
            )
            _write_json(
                f"competitors/{cid}/cadence.json", _get(client, f"/competitors/{cid}/cadence")
            )

        # Reports: list + each body + a rendered PDF (served as a static file).
        reports = _get(client, "/reports")
        _write_json("reports.json", reports)
        for r in reports:
            rid = r["id"]
            _write_json(f"reports/{rid}.json", _get(client, f"/reports/{rid}"))
            pdf = client.get(f"/reports/{rid}/pdf")
            if pdf.status_code == 200:
                _write_bytes(f"reports/{rid}.pdf", pdf.content)

    print("Done.")


if __name__ == "__main__":
    main()
