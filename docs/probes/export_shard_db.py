"""Export each shard database of a measurement run a row per line.

    python docs/probes/export_shard_db.py OUT_DIR

The runner (docs/probes/short_workflows_measurement.py) writes one sqlite
database per shard, OUT_DIR/shard-N.db. The databases are git-ignored, so
their rows are kept as OUT_DIR/phases-shard-N.jsonl: one line per workflow
row and one per phase row, each workflow line citing its database's sha256,
and each phase's verdict as JSON. Copied byte-identical into docs/traces/.
Free: it reads sqlite files and calls nothing.
"""
from __future__ import annotations

import glob
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

out = Path(sys.argv[1])
for db in sorted(glob.glob(str(out / "shard-*.db"))):
    n = Path(db).stem.split("-")[1]
    sha = hashlib.sha256(Path(db).read_bytes()).hexdigest()
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    with (out / f"phases-shard-{n}.jsonl").open("w", encoding="utf-8") as f:
        for r in con.execute("select id, request, status, risk_level, total_cost, "
                             "unreconciled_liability, error, created_at "
                             "from workflows order by id"):
            f.write(json.dumps({"kind": "workflow", "source_db_sha256": sha,
                                **dict(r)}) + "\n")
        for r in con.execute("select id, workflow_id, phase, iteration, model_used, "
                             "cost, created_at, verdict_json from phase_results "
                             "order by id"):
            row = dict(r)
            raw = row.pop("verdict_json")
            try:
                verdict = json.loads(raw)
            except ValueError:
                verdict = raw
            f.write(json.dumps({"kind": "phase", **row, "verdict": verdict}) + "\n")
    print(n, sha)
