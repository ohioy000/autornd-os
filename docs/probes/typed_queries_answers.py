"""Full answers to the inspection-authorization request, with and without
the typed search queries. Paid.

    ARM=now|typed_queries python docs/probes/typed_queries_answers.py \\
        OUT_DIR REPEATS MAX_SPEND

It runs docs/probes/short_workflows_measurement.py unchanged on golden's
side test through answer-and-recompute, the default workflow. With
ARM=typed_queries it first puts typed_queries_sweep.py's wrapper in place of
analyze_request, so the lookup asks the typed queries. Main is not changed.
The golden screen is recorded and is not the result: the answers are read
by hand (D50).
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = os.environ.get("ARM", "now")
out, repeats, max_spend = sys.argv[1:4]
os.environ["MEASURE_SET"] = "golden"
os.environ["MEASURE_WORKFLOWS"] = "answer-and-recompute"
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))
if ARM == "typed_queries":
    import typed_queries_sweep as sweep
    from autornd.knowledge import context as ctx

    ctx.analyze_request = sweep.typed_queries
elif ARM != "now":
    raise SystemExit(f"ARM {ARM!r} is not now or typed_queries")
sys.argv = ["short_workflows_measurement.py", out, "0", "1", repeats,
            max_spend, "IA"]
runpy.run_path(str(HERE / "short_workflows_measurement.py"), run_name="__main__")
