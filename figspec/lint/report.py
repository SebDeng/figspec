"""Finding formatting: terminal text and machine-readable JSON."""
from __future__ import annotations
from dataclasses import asdict
from figspec import __version__

_ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}

def summarize(findings, strict: bool) -> dict:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for f in findings:
        counts[f.level] += 1
    ready = counts["FAIL"] == 0 and (not strict or counts["WARN"] == 0)
    return {"ready": ready, "strict": strict, "counts": counts}

def render_text(source: str, findings, summary, max_evidence: int = 10) -> str:
    lines = [f"figspec lint {source}"]
    for f in sorted(findings, key=lambda f: (_ORDER[f.level], f.check_id)):
        lines.append(f"[{f.level}] {f.check_id}: {f.message}")
        shown = f.evidence[:max_evidence]
        for ev in shown:
            lines.append(f"  - {ev}")
        hidden = len(f.evidence) - len(shown)
        if hidden > 0:
            lines.append(f"  ({hidden} more evidence lines in --json output)")
    c = summary["counts"]
    lines.append(f"summary: {c['PASS']} pass, {c['WARN']} warn, {c['FAIL']} fail")
    lines.append("verdict: " + ("READY FOR SUBMISSION" if summary["ready"]
                                else "FIX BEFORE SUBMISSION"))
    lines.append("note: figspec lint checks the finished artifact geometry; "
                 "it does not validate scientific content")
    return "\n".join(lines)

def render_json(source: str, findings, summary) -> dict:
    items = []
    for f in sorted(findings, key=lambda f: (_ORDER[f.level], f.check_id)):
        d = asdict(f)
        d.pop("boxes_pt", None)
        if d.get("page") is not None:
            d["page"] = d["page"] + 1  # 1-indexed for humans/agents
        items.append(d)
    return {"source": source,
            "tool": {"name": "figspec", "version": __version__},
            "summary": summary,
            "findings": items}

def exit_code(summary) -> int:
    return 0 if summary["ready"] else 1
