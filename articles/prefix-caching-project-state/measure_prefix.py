#!/usr/bin/env python3
"""Measure how much of a project record survives as a reusable prompt prefix.

Prompt caches match from the start of a request and stop at the first byte that
differs. So what decides reuse is not how much of your context repeats, it is
WHERE the first change falls.

This takes two versions of the same project record, one before a change and one
after, and reports how many bytes at the front are identical in two renderings:

  the record as stored     ordered for custody, identity and revision first
  a compiled projection    ordered by volatility, slowest material first and
                           the revision and integrity hash last

Standard library only. No network. Run it on the sample pair in sample/ or on
any two JSON files of the same shape.

    python measure_prefix.py sample/before.json sample/after.json

WHAT THIS IS NOT
----------------
It is not a cache simulator and it reports no saving. Prefix share is the
property a cache needs, not the money it returns: caches have minimum sizes and
expiry windows, and the counter reporting a cache read is visible only on a raw
API path. Bytes and characters here are exact; tokens are estimated at a stated
characters-per-token and labelled as estimates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

LIVE = {"accepted"}
OPEN_TASK = {"planned", "active", "blocked"}


def canonical(record: dict) -> str:
    """Serialise the way a project record is normally stored and hashed."""
    return json.dumps(record, indent=2, ensure_ascii=False) + "\n"


def integrity(record: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()


def block(label: str, rows: list[str]) -> list[str]:
    return [label] + rows + [""] if rows else []


def project(record: dict) -> str:
    """Render the active view, slowest moving material first.

    The order is the whole point. Identity, objective and authority almost never
    change. Constraints, accepted requirements and decisions change slowly.
    Open questions and live tasks change often. The revision and the integrity
    hash change on every single accepted change, so they go last, where changing
    them costs the least.
    """
    out: list[str] = [
        "# PROJECT",
        f"record: {record.get('contract_id')}  format: {record.get('lpc_version')}",
        f"title: {record.get('title')}",
        "",
    ]
    objective = record.get("objective") or {}
    if objective.get("statement"):
        out += ["# OBJECTIVE", objective["statement"], ""]
    for name, field in (("DELIVERABLES", "deliverables"), ("SUCCESS CRITERIA", "success_criteria")):
        out += block(f"# {name}", [f"- {d.get('text', d) if isinstance(d, dict) else d}"
                                   for d in objective.get(field, [])])

    authority = record.get("authority") or {}
    if authority:
        out += ["# AUTHORITY",
                f"owner: {authority.get('owner')}  model may propose: {authority.get('model_may_propose')}",
                "requires the owner: " + ", ".join(authority.get("approval_required_for", [])),
                ""]

    out += block("# CONSTRAINTS",
                 [f"- {c.get('text')}" for c in record.get("constraints", []) if isinstance(c, dict)])
    out += block("# ACCEPTED REQUIREMENTS",
                 [f"- {r['id']}: {r.get('text')}" for r in record.get("requirements", [])
                  if isinstance(r, dict) and r.get("status") in LIVE])
    out += block("# ACCEPTED DECISIONS",
                 [f"- {d['id']}: {d.get('text')}" for d in record.get("decisions", [])
                  if isinstance(d, dict) and d.get("status", "accepted") in LIVE])
    out += block("# ACCEPTANCE CRITERIA",
                 [f"- {a['id']} [{a.get('status')}]: {a.get('text')}"
                  for a in record.get("acceptance_criteria", []) if isinstance(a, dict)])
    out += block("# ACCEPTED FINDINGS",
                 [f"- {f['id']}: {f.get('text')}" for f in record.get("findings", [])
                  if isinstance(f, dict) and f.get("status") in LIVE])
    out += block("# OPEN HIGH-PRIORITY QUESTIONS",
                 [f"- {u['id']}: {u.get('question')}" for u in record.get("unknowns", [])
                  if isinstance(u, dict) and u.get("status") == "open"
                  and u.get("priority") in {"high", "critical"}])
    out += block("# LIVE TASKS",
                 [f"- {t['id']} [{t.get('status')}] {t.get('text')}"
                  for t in record.get("tasks", []) if isinstance(t, dict)
                  and t.get("status") in OPEN_TASK])

    state = record.get("project_state") or {}
    out += ["# STATE",
            f"phase: {state.get('phase')}  readiness: {state.get('readiness')}  "
            f"outcome: {state.get('outcome_status')}",
            "",
            # Last on purpose. Anything placed after these can never be cached,
            # because these two change every time the record changes.
            "# CUSTODY",
            f"revision: {record.get('revision')}",
            f"integrity: {integrity(record)}",
            ""]
    return "\n".join(out)


def common_prefix(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def first_difference(a: str, b: str, at: int) -> str:
    """The text around the point where the two renderings part company."""
    head = b[:at]
    line_start = head.rfind("\n") + 1
    line_end = b.find("\n", at)
    line = b[line_start:line_end if line_end != -1 else len(b)]
    column = at - line_start
    return f"{line[:column]} <HERE> {line[column:]}".strip()


def report(label: str, before: str, after: str, cpt: float) -> int:
    a, b = before.encode("utf-8"), after.encode("utf-8")
    shared = common_prefix(a, b)
    share = shared / len(b) if b else 0
    print(f"{label:<34}{len(b):>9,}{shared:>10,}{share:>9.1%}{round(len(after) / cpt):>10,}")
    return shared


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before", help="the project record before an accepted change")
    ap.add_argument("after", help="the same record after it")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="stated assumption for the token ESTIMATE; the share does not depend on it")
    args = ap.parse_args(argv)

    before = json.loads(Path(args.before).read_text(encoding="utf-8-sig"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8-sig"))

    print(f"before: revision {before.get('revision')}   after: revision {after.get('revision')}")
    print(f"tokens are ESTIMATES at {args.chars_per_token} chars/token; bytes are exact\n")
    print(f"{'rendering':<34}{'bytes':>9}{'reusable':>10}{'share':>9}{'tokens~':>10}")

    report("record as stored, custody first", canonical(before), canonical(after),
           args.chars_per_token)
    p_before, p_after = project(before), project(after)
    shared = report("projection, volatility order", p_before, p_after, args.chars_per_token)

    print(f"\nthe projection is {len(p_after) / len(canonical(after)):.1%} the size of the record")
    print("\nthe projection's reusable prefix ends here:")
    print(f"  {first_difference(p_before, p_after, shared)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
