#!/usr/bin/env python3
"""Experiment B — analysis readiness of three task representations.

For every case and every question, each representation is asked on its own
terms and its answer is scored against the gold answer computed by exact
automata analysis of the coordinator formula:

    correct       the answer matches gold
    inconclusive  a bounded method found no witness where none is required
                  to exist within its bound, or reported "unknown"
    wrong         the answer contradicts gold
    n/a           the question is not typeable against this artifact
                  (no requirement units) or does not apply to the case

Outputs ``results/analysis_readiness.csv`` (one row per case × question ×
representation) and ``results/summary.csv`` (question × representation).
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import environment as E  # noqa: E402
from src import queries as Q  # noqa: E402
from src.cases import Case, all_cases  # noqa: E402

RESULTS = ROOT / "results"
REPRESENTATIONS = ("a1", "a2c", "a3")
COLUMNS = [
    "case_id", "case_class", "query", "representation", "artifact_source",
    "support_mode", "answer", "gold_answer", "verdict", "witness", "work",
    "bound", "provenance_units", "gold_units", "runtime_ms", "note",
]


def _fmt(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (tuple, list)):
        return json.dumps(list(value))
    return str(value)


def _verdict(query: str, answer: Q.Answer, gold: Q.Answer) -> str:
    if answer.support_mode in ("no_provenance", "not_applicable"):
        return "n/a"
    if answer.support_mode == "bounded_only":
        if query in ("B1", "B4"):
            if answer.answer is True:
                return "correct" if gold.answer is True else "wrong"
            return "inconclusive"
        if query == "B3":
            g = dict(gold.answer)
            for k, v in dict(answer.answer).items():
                if v == "fires" and g[k] != "fires":
                    return "wrong"
            return "correct" if all(v == "fires" for v in dict(answer.answer).values()) and all(
                g[k] == "fires" for k in dict(answer.answer)
            ) else "inconclusive"
        if query == "B7":
            bounded = str(answer.answer).replace("_up_to_bound", "")
            return "correct" if bounded == gold.answer else ("inconclusive" if "equivalent" in bounded else "wrong")
    return "correct" if _fmt(answer.answer) == _fmt(gold.answer) else "wrong"


def run_case(case: Case, grid: E.Grid) -> list[dict]:
    rows = []
    gold = Q.handle(case, "gold")
    gold_answers = {
        "B1": Q.b1(gold), "B2": Q.b2(gold), "B3": Q.b3(gold, case.task), "B4": Q.b4(gold, grid),
        "B5": Q.b5(gold), "B6": Q.b6(gold, grid), "B8": Q.b8(gold),
    }
    if case.partner is not None:
        gold_answers["B7"] = Q.b7(gold, Q.handle(case.partner, "gold"))

    for rep in REPRESENTATIONS:
        h = Q.handle(case, rep)
        source = getattr(case, rep).source
        answers = {
            "B1": Q.b1(h), "B2": Q.b2(h), "B3": Q.b3(h, case.task), "B4": Q.b4(h, grid),
            "B5": Q.b5(h), "B6": Q.b6(h, grid), "B8": Q.b8(h),
        }
        if case.partner is not None:
            answers["B7"] = Q.b7(h, Q.handle(case.partner, rep))
        for query in Q.QUERIES:
            if query not in answers:
                continue
            a, g = answers[query], gold_answers[query]
            rows.append(
                {
                    "case_id": case.case_id, "case_class": case.case_class, "query": query,
                    "representation": rep, "artifact_source": source,
                    "support_mode": a.support_mode, "answer": _fmt(a.answer),
                    "gold_answer": _fmt(g.answer), "verdict": _verdict(query, a, g),
                    "witness": _fmt(a.witness), "work": a.work, "bound": a.bound,
                    "provenance_units": _fmt(a.provenance_units), "gold_units": Q.gold_units(case),
                    "runtime_ms": a.runtime_ms, "note": a.note,
                }
            )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["query"], r["representation"]].append(r)
    out = []
    for (query, rep), items in sorted(groups.items()):
        verdicts = Counter(r["verdict"] for r in items)
        modes = Counter(r["support_mode"] for r in items)
        timed = [float(r["runtime_ms"]) for r in items if r["support_mode"] not in ("no_provenance", "not_applicable")]
        out.append(
            {
                "query": query, "representation": rep, "cases": len(items),
                "correct": verdicts["correct"], "inconclusive": verdicts["inconclusive"],
                "wrong": verdicts["wrong"], "n_a": verdicts["n/a"],
                "native_exact": modes["native_exact"], "adapter_exact": modes["adapter_exact"],
                "bounded_only": modes["bounded_only"], "no_provenance": modes["no_provenance"],
                "mean_runtime_ms": round(sum(timed) / len(timed), 2) if timed else "",
                "max_runtime_ms": round(max(timed), 2) if timed else "",
            }
        )
    return out


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    grid = E.blocked_map()
    cases = all_cases()
    rows: list[dict] = []
    for index, case in enumerate(cases, start=1):
        rows.extend(run_case(case, grid))
        print(f"[{index:2d}/{len(cases)}] {case.case_id:12s} {case.case_class}", flush=True)

    with (RESULTS / "analysis_readiness.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    summary = summarize(rows)
    with (RESULTS / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]), lineterminator="\n")
        w.writeheader(); w.writerows(summary)

    (RESULTS / "metadata.json").write_text(
        json.dumps(
            {
                "pilot": "pilot_2_0_analysis_readiness",
                "python": sys.version.split()[0], "platform": platform.platform(),
                "cases": len(cases), "rows": len(rows), "map": grid.name,
                "bounds": {"H_ENUM": Q.H_ENUM, "H_PATH": Q.H_PATH, "REPAIR_DEPTH": Q.REPAIR_DEPTH,
                            **Q.enumeration_budget()},
                "queries": Q.DESCRIPTIONS,
                "artifact_sources": Counter(f"{r['representation']}:{r['artifact_source']}" for r in rows if r["query"] == "B1"),
            },
            indent=2, sort_keys=True,
        ) + "\n", encoding="utf-8",
    )
    digest = "\n".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
        for p in sorted(RESULTS.glob("*")) if p.is_file() and p.name != "checksums.sha256"
    )
    (RESULTS / "checksums.sha256").write_text(digest + "\n", encoding="utf-8")

    print(f"\n{'query':5s} {'rep':4s} {'n':>3s} {'ok':>3s} {'inc':>3s} {'wr':>3s} {'n/a':>3s}  mode")
    for s in summary:
        mode = "native" if s["native_exact"] else "adapter" if s["adapter_exact"] else "bounded" if s["bounded_only"] else "noprov"
        print(f"{s['query']:5s} {s['representation']:4s} {s['cases']:>3d} {s['correct']:>3d} {s['inconclusive']:>3d} {s['wrong']:>3d} {s['n_a']:>3d}  {mode:8s} {s['mean_runtime_ms']}ms")


if __name__ == "__main__":
    main()
