#!/usr/bin/env python3
"""MANUAL operator diagnostic -- NOT a registered hook (do not add to settings.json).

Same instrument shape as .claude/hooks/context-ratchet.sh: a post-hoc reading an
operator or agent runs by hand, pointed at a dispatch's transcripts instead of at
the configuration tree.

Extracts STEERING and SELF-CORRECTION candidates from a dispatch session so the
prune-falsification obligation in claude-architect's model-behavior-reference.md
(Application checklist item 4) can be discharged with numbers rather than
impressions.

It emits CANDIDATES and counts, never verdicts. Every candidate needs a human or
agent read before it counts -- .claude/rules/tool-output-integrity.md Prohibition 3
("grep finds candidates; only a clean Read confirms") binds this instrument as much
as anything else. The prefilter is deliberately WIDE: an over-match arrives visibly
and gets dispositioned, an under-match is indistinguishable from absence.

Usage:
    python3 .claude/hooks/dispatch-telemetry.py <session-id> [<session-id> ...]
    python3 .claude/hooks/dispatch-telemetry.py --list         # recent sessions
    python3 .claude/hooks/dispatch-telemetry.py <id> --full    # longer snippets

Transcripts: ~/.claude/projects/-workspaces-baseball-crawl/<session-id>.jsonl plus
that session's <session-id>/subagents/agent-*.jsonl and their .meta.json siblings.
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path.home() / ".claude" / "projects" / "-workspaces-baseball-crawl"

# --- Prefilter cues -----------------------------------------------------------
# Wide on purpose. Each cue produces a CANDIDATE for adjudication, not a finding.

STEER_CUES = [
    r"\byou (?:were|are) wrong\b", r"\bthat(?:'s| is) (?:wrong|incorrect|not right)\b",
    r"\bincorrect\b", r"\bdo not\b", r"\bdon't\b", r"\bstop\b", r"\bundo\b",
    r"\brevert\b", r"\bredo\b", r"\bre-?do\b", r"\byou missed\b", r"\bmissed\b",
    r"\byou should have\b", r"\bshould have\b", r"\binstead\b", r"\bcorrection\b",
    r"\bcorrect (?:the|this|that|it)\b", r"\bfix (?:the|this|that|it)\b",
    r"\bno[,.—-]", r"\bnot what\b", r"\bwrong\b", r"\bviolat", r"\bout of scope\b",
    r"\byou (?:did|have) not\b", r"\bfailed to\b", r"\bre-?read\b", r"\bruling\b",
]

# Lead concedes to the agent: the agent CAUGHT something. Negative-signal bucket.
UPHELD_CUES = [
    r"\byour (?:refusal|objection|substitution|catch|push-?back|correction) (?:was|is)\b",
    r"\bmy instruction was wrong\b", r"\bi was wrong\b", r"\byou (?:were|are) right\b",
    r"\bupholding\b", r"\bupheld\b", r"\baccepted\b", r"\bgood catch\b",
]

# Assignment / lifecycle traffic: never steering.
ASSIGN_CUES = [
    r"\byou are (?:claude-architect|software-engineer|the |a )", r"\bspawn(?:ed)? (?:for|as)\b",
    r"\bstory E-\d+-\d+\b.*\b(?:assign|begin|start|proceed)\b",
    r"\bproceed\b", r"\bauthoriz", r"\bapproved\b", r"\bshutdown\b",
]

SELFCORR_CUES = [
    r"\bi (?:was|am) wrong\b", r"\bi got (?:that|this|it) wrong\b",
    r"\bmy (?:mistake|error)\b", r"\bi mis(?:read|stated|counted|took|understood|attributed)",
    r"\bcorrection\b", r"\bi need to correct\b", r"\bi (?:must |should )?retract\b",
    r"\bretract(?:ing|ion)?\b", r"\bon re-?read(?:ing)?\b", r"\bre-?reading\b",
    r"\bthat was wrong\b", r"\bi (?:previously |earlier )?(?:said|claimed|reported|asserted)\b.*\bbut\b",
    r"\bstrike that\b", r"\bscratch that\b", r"\bactually,", r"\bi overstated\b",
    r"\bi understated\b", r"\bwithdraw\b", r"\bamend(?:ing|ment)?\b",
    r"\bi had (?:it|that|this) backwards\b", r"\bcaught (?:my|myself)\b",
]

# Review gate traffic: the process working as designed. Counted SEPARATELY,
# excluded from steering.
GATE_CUES = [
    r"\bAC-\d+\b", r"\bFAIL(?:S|ED)?\b", r"\bPASS(?:ES|ED)?\b", r"\bfinding\b",
    r"\bBLOCKER\b", r"\bMUST-FIX\b", r"\bAPPROVED\b", r"\breview\b",
]

GATE_AGENTS = ("code-reviewer", "product-manager")

TEAMMATE_RE = re.compile(r'<teammate-message teammate_id="([^"]*)"(?: color="[^"]*")?(?: summary="([^"]*)")?', re.S)
RELAY_RE = re.compile(r"^Another Claude session sent a message:")


def compile_any(cues):
    return re.compile("|".join(cues), re.I)


STEER_RE = compile_any(STEER_CUES)
UPHELD_RE = compile_any(UPHELD_CUES)
ASSIGN_RE = compile_any(ASSIGN_CUES)
SELFCORR_RE = compile_any(SELFCORR_CUES)
GATE_RE = compile_any(GATE_CUES)


def text_of(msg):
    """Flatten a message's content blocks to plain text."""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return "\n".join(out)


def read_jsonl(path):
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def scan_transcript(path, is_subagent):
    """Return (inbound, outbound, models) for one transcript."""
    inbound, outbound, models = [], [], set()
    for rec in read_jsonl(path):
        rtype = rec.get("type")
        ts = rec.get("timestamp", "")
        msg = rec.get("message", {}) or {}
        if rtype == "assistant":
            model = msg.get("model")
            if model:
                models.add(model)
            txt = text_of(msg)
            if txt.strip():
                outbound.append((ts, txt))
        elif rtype == "user" and not rec.get("isMeta"):
            txt = text_of(msg)
            if not txt.strip():
                continue
            inbound.append((ts, txt))
    return inbound, outbound, models


def classify_inbound(txt):
    """Bucket an inbound message. Returns (bucket, matched_cue)."""
    head = txt[:2500]
    m = UPHELD_RE.search(head)
    if m:
        return "UPHELD", m.group(0)
    m = STEER_RE.search(head)
    if m:
        return "STEER?", m.group(0)
    m = ASSIGN_RE.search(head)
    if m:
        return "ASSIGN", m.group(0)
    return "ROUTINE", ""


def sender_of(txt):
    m = TEAMMATE_RE.search(txt)
    if m:
        return m.group(1) or "?", (m.group(2) or "")
    if RELAY_RE.match(txt):
        return "relay", ""
    return "OPERATOR", ""


def is_idle_notification(txt):
    return '"type":"idle_notification"' in txt or '"type": "idle_notification"' in txt


LIFECYCLE_MARKERS = (
    '"type":"shutdown_', '"type": "shutdown_', '"type":"teammate_terminated"',
    '"type":"plan_approval', "has shut down.",
)
CONTINUATION_MARKER = "This session is being continued from a previous conversation"


def is_lifecycle(txt):
    return any(mk in txt for mk in LIFECYCLE_MARKERS) or txt.startswith(CONTINUATION_MARKER)


def snippet(txt, width):
    body = TEAMMATE_RE.sub("", txt).strip()
    body = re.sub(r"\s+", " ", body)
    return body[:width]


def scan_session(session_id, width):
    main_path = PROJECT_DIR / f"{session_id}.jsonl"
    if not main_path.exists():
        sys.exit(f"ERROR: no transcript at {main_path}")

    agents = []  # (name, custom_type, alias_model, effective_models, inbound, outbound)

    inbound, outbound, models = scan_transcript(main_path, is_subagent=False)
    agents.append(("main", "main-session", "(harness)", models, inbound, outbound))

    sub_dir = PROJECT_DIR / session_id / "subagents"
    if sub_dir.is_dir():
        for jf in sorted(sub_dir.glob("agent-*.jsonl")):
            meta_path = jf.with_suffix("").with_suffix(".meta.json")
            if not meta_path.exists():
                meta_path = Path(str(jf)[: -len(".jsonl")] + ".meta.json")
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except json.JSONDecodeError:
                    meta = {}
            i, o, m = scan_transcript(jf, is_subagent=True)
            agents.append((
                meta.get("name", jf.stem),
                meta.get("customAgentType", meta.get("agentType", "?")),
                meta.get("model", "?"),
                m, i, o,
            ))

    print(f"# Dispatch telemetry -- session {session_id}")
    print()
    print("Candidates only. Adjudicate every row before counting it "
          "(tool-output-integrity.md Prohibition 3).")
    print()

    print("## Roster and execution profile")
    print()
    print("| Agent | Definition | Alias | Effective model(s) | Inbound | Turns |")
    print("|---|---|---|---|---|---|")
    for name, ctype, alias, models, i, o in agents:
        eff = ", ".join(sorted(models)) or "-"
        real_in = [x for x in i if not is_idle_notification(x[1])]
        print(f"| {name} | {ctype} | {alias} | {eff} | {len(real_in)} | {len(o)} |")
    print()

    totals = {"OP-STEER?": 0, "STEER?": 0, "UPHELD": 0, "ASSIGN": 0, "ROUTINE": 0,
              "GATE": 0, "SPAWN": 0, "LIFECYCLE": 0, "SELFCORR?": 0, "turns": 0}

    print("## Inbound candidates (steering surface)")
    print()
    for name, ctype, alias, _models, inb, out in agents:
        totals["turns"] += len(out)
        rows = []
        first_seen = False
        for ts, txt in inb:
            if is_idle_notification(txt):
                continue
            sender, summary = sender_of(txt)
            # The first real inbound to a subagent is its spawn brief, never steering.
            if name != "main" and not first_seen:
                first_seen = True
                totals["SPAWN"] += 1
                continue
            if is_lifecycle(txt):
                totals["LIFECYCLE"] += 1
                continue
            bucket, cue = classify_inbound(txt)
            gate = bool(GATE_RE.search(txt[:2500])) and (
                ctype in GATE_AGENTS or sender.startswith(("cr-", "pm-", "acr-", "apm-")))
            if gate and bucket in ("STEER?", "ROUTINE"):
                bucket = "GATE"
            if bucket == "STEER?" and sender == "OPERATOR":
                bucket = "OP-STEER?"
            totals[bucket] = totals.get(bucket, 0) + 1
            if bucket in ("ROUTINE", "ASSIGN"):
                continue
            rows.append((ts, sender, bucket, cue, summary, snippet(txt, width)))
        if not rows:
            continue
        print(f"### {name} ({ctype}, {alias})")
        print()
        for ts, sender, bucket, cue, summary, snip in rows:
            print(f"- **{bucket}** `{ts}` from `{sender}` — cue `{cue}`")
            if summary:
                print(f"  - summary: {summary}")
            print(f"  - {snip}")
        print()

    print("## Self-correction candidates (agent's own turns)")
    print()
    for name, ctype, alias, _models, _inb, out in agents:
        rows = []
        for ts, txt in out:
            m = SELFCORR_RE.search(txt)
            if not m:
                continue
            idx = max(0, m.start() - 120)
            rows.append((ts, m.group(0), re.sub(r"\s+", " ", txt[idx:idx + width])))
        totals["SELFCORR?"] += len(rows)
        if not rows:
            continue
        print(f"### {name} ({ctype}, {alias}) — {len(rows)} candidate(s)")
        print()
        for ts, cue, snip in rows:
            print(f"- `{ts}` cue `{cue}`: …{snip}…")
        print()

    print("## Counts (pre-adjudication)")
    print()
    print("| Bucket | Count |")
    print("|---|---|")
    for k in ("OP-STEER?", "STEER?", "UPHELD", "GATE", "SELFCORR?",
              "SPAWN", "LIFECYCLE", "ASSIGN", "ROUTINE"):
        print(f"| {k} | {totals.get(k, 0)} |")
    print(f"| agent turns (denominator) | {totals['turns']} |")
    print()
    print("Normalize by agent turns and by story count before comparing dispatches; "
          "raw counts are not comparable across epics of different size.")


def list_sessions():
    rows = []
    for p in PROJECT_DIR.glob("*.jsonl"):
        subs = PROJECT_DIR / p.stem / "subagents"
        n = len(list(subs.glob("agent-*.jsonl"))) if subs.is_dir() else 0
        rows.append((p.stat().st_mtime, p.stem, p.stat().st_size, n))
    rows.sort(reverse=True)
    print(f"{'session':40} {'MB':>6} {'agents':>7}  modified")
    for mtime, sid, size, n in rows[:30]:
        import datetime
        ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{sid:40} {size/1e6:6.1f} {n:7d}  {ts}")


def main():
    args = [a for a in sys.argv[1:]]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return
    if "--list" in args:
        list_sessions()
        return
    width = 400 if "--full" in args else 200
    for sid in [a for a in args if not a.startswith("-")]:
        scan_session(sid, width)
        print()


if __name__ == "__main__":
    main()
