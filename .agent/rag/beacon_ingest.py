#!/usr/bin/env python3
"""
Beacon Ingest - Pont local Beacon -> mémoire unifiée Hephaistos.

Lit le journal Beacon (~/.beacon/endpoint/logs/runtime.jsonl), distille les
sessions d'agents en documents synthétiques, puis les injecte dans le pipeline
RAG (chunking, tagging, embeddings zvec/qdrant, relations KG memory_mcp.db).

100 % local : aucun appel réseau, aucune clé API requise (contrairement à
`beacon memory evaluations run` qui exige le service Jev de TypeSafe).

Traitement incrémental : un fichier d'état mémorise l'offset JSONL pour ne
traiter que les nouveaux événements à chaque run.

Usage:
    python beacon_ingest.py --once            # run unique (défaut)
    python beacon_ingest.py --dry-run         # aperçu sans écriture
    python beacon_ingest.py --limit 10        # max N sessions par run
    python beacon_ingest.py --reset           # repartir de zéro
    python beacon_ingest.py --log-path X      # chemin runtime.jsonl alternatif
"""

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STATE_FILE = Path(__file__).resolve().parent.parent / "scripts" / ".beacon-offset.json"
DEFAULT_LOG = Path.home() / ".beacon" / "endpoint" / "logs" / "runtime.jsonl"
MAX_SESSIONS_DEFAULT = 20
MAX_MSG_CHARS = 300
MAX_SESSION_DOC_CHARS = 8000


def _env_db_root(project_root: Path) -> None:
    """Charge AGENT_DB_ROOT depuis le .env du projet (comme start-workspace.ps1)."""
    env_file = project_root / ".env"
    if env_file.exists() and not os.environ.get("AGENT_DB_ROOT"):
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "AGENT_DB_ROOT" and value.strip():
                os.environ["AGENT_DB_ROOT"] = value.strip().strip('"').strip("'")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            state.setdefault("done", [])
            return state
        except (json.JSONDecodeError, OSError):
            pass
    return {"offset": 0, "done": []}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _iter_events(log_path: Path, offset: int):
    """Itère les événements JSONL à partir de l'offset. Retourne (events, new_offset)."""
    events = []
    with open(log_path, "rb") as f:
        f.seek(offset)
        for raw in f:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        new_offset = f.tell()
    return events, new_offset


def _distill_sessions(events: list) -> dict:
    """Groupe les événements par session.id et construit un résumé par session."""
    sessions = defaultdict(lambda: {
        "harness": None, "repository": None, "cwd": None,
        "t_start": None, "t_end": None,
        "prompts": [], "commands": [], "files": set(), "tools": defaultdict(int),
        "mcp": defaultdict(int), "errors": [],
    })
    for e in events:
        sess = e.get("session") or {}
        sid = sess.get("id") or "unknown"
        s = sessions[sid]
        s["harness"] = s["harness"] or (e.get("harness") or {}).get("name")
        s["repository"] = s["repository"] or e.get("repository")
        s["cwd"] = s["cwd"] or sess.get("working_directory")
        ts = e.get("timestamp")
        if ts:
            s["t_start"] = ts if not s["t_start"] or ts < s["t_start"] else s["t_start"]
            s["t_end"] = ts if not s["t_end"] or ts > s["t_end"] else s["t_end"]
        action = (e.get("event") or {}).get("action", "")
        msg = (e.get("message") or "")[:MAX_MSG_CHARS]
        if e.get("severity") in ("error", "critical", "warning") and msg:
            s["errors"].append(msg)
        if action == "prompt.submitted":
            prompt = (e.get("prompt") or {}).get("content") or msg
            if prompt:
                s["prompts"].append(prompt[:MAX_MSG_CHARS])
        elif action == "command.executed":
            cmd = ((e.get("raw") or {}).get("command") or msg)
            if cmd:
                s["commands"].append(cmd[:MAX_MSG_CHARS])
        elif action in ("file.modified", "file.read"):
            fp = (e.get("file") or {}).get("path")
            if fp and action == "file.modified":
                s["files"].add(fp)
        elif action == "tool.invoked":
            name = (e.get("tool") or {}).get("name") or "unknown"
            s["tools"][name] += 1
        elif action == "mcp.tool_invoked":
            name = (e.get("mcp") or {}).get("tool") or "unknown"
            s["mcp"][name] += 1
    return sessions


def _session_to_doc(sid: str, s: dict) -> str:
    """Rend un document markdown distillé pour une session."""
    lines = [
        f"# Agent session digest: {sid}",
        f"- Harness: {s['harness'] or 'unknown'}",
        f"- Repository: {s['repository'] or 'unknown'}",
        f"- Working dir: {s['cwd'] or 'unknown'}",
        f"- Period: {s['t_start'] or '?'} -> {s['t_end'] or '?'}",
        "",
    ]
    if s["prompts"]:
        lines.append("## User prompts")
        lines += [f"- {p}" for p in s["prompts"][:20]]
        lines.append("")
    if s["files"]:
        lines.append("## Files modified")
        lines += [f"- {f}" for f in sorted(s["files"])[:30]]
        lines.append("")
    if s["tools"]:
        top = sorted(s["tools"].items(), key=lambda x: -x[1])[:15]
        lines.append("## Tools used")
        lines += [f"- {n} x{c}" for n, c in top]
        lines.append("")
    if s["mcp"]:
        top = sorted(s["mcp"].items(), key=lambda x: -x[1])[:15]
        lines.append("## MCP calls")
        lines += [f"- {n} x{c}" for n, c in top]
        lines.append("")
    if s["errors"]:
        lines.append("## Errors / warnings observed")
        lines += [f"- {e}" for e in s["errors"][:15]]
        lines.append("")
    if s["commands"]:
        lines.append("## Commands executed")
        lines += [f"- `{c}`" for c in s["commands"][:25]]
    return "\n".join(lines)[:MAX_SESSION_DOC_CHARS]


async def run(args) -> int:
    project_root = Path(__file__).resolve().parents[2]
    _env_db_root(project_root)

    log_path = Path(args.log_path).expanduser() if args.log_path else DEFAULT_LOG
    if not log_path.exists():
        print(f"[beacon] Pas de journal Beacon: {log_path} — rien à faire.")
        return 0

    state = {"offset": 0, "done": []} if args.reset else _load_state()
    done = set(state["done"])
    events, new_offset = _iter_events(log_path, state["offset"])
    if not events:
        print("[beacon] Aucun nouvel événement depuis le dernier run.")
        return 0

    sessions = _distill_sessions(events)
    # On ignore les sessions vides (pas de prompt/fichier/commande)
    # et celles déjà indexées lors d'un run précédent
    sessions = {
        sid: s for sid, s in sessions.items()
        if (s["prompts"] or s["files"] or s["commands"]) and sid not in done
    }
    if not sessions:
        print(f"[beacon] {len(events)} événements lus, aucune session nouvelle significative.")
        if not args.dry_run:
            state["offset"] = new_offset
            _save_state(state)
        return 0

    ordered = sorted(sessions.items(), key=lambda kv: kv[1]["t_start"] or "")
    to_process = ordered[-args.limit:]
    backlog = len(ordered) - len(to_process)
    print(f"[beacon] {len(events)} événements, {len(sessions)} sessions nouvelles, "
          f"{len(to_process)} à indexer (limite {args.limit}, backlog {backlog}).")

    if args.dry_run:
        for sid, s in to_process:
            print(f"--- {sid} [{s['harness']}] repo={s['repository']} "
                  f"prompts={len(s['prompts'])} files={len(s['files'])}")
        return 0

    from pipeline import RAGPipeline
    pipeline = RAGPipeline()
    ok, fail = 0, 0
    for sid, s in to_process:
        doc = _session_to_doc(sid, s)
        try:
            report = await pipeline.index_document(
                content=doc,
                doc_type="markdown",
                source_file=f"beacon://{s['harness'] or 'unknown'}/{sid}",
                metadata={
                    "source": "beacon",
                    "harness": s["harness"],
                    "session_id": sid,
                    "repository": s["repository"],
                    "period_start": s["t_start"],
                    "period_end": s["t_end"],
                },
            )
            if report.get("status") == "success":
                ok += 1
                done.add(sid)
                print(f"[beacon] session {sid}: {report['chunks_created']} chunks, "
                      f"{report['memory_relations']} relations mémoire")
            else:
                fail += 1
                print(f"[beacon] session {sid}: erreurs {report['errors'][:2]}")
        except Exception as e:
            fail += 1
            print(f"[beacon] session {sid}: exception {e}")

    # L'offset n'avance que si tout le backlog a été traité — sinon le prochain
    # run relit les événements et retrouve les sessions restantes via `done`.
    if backlog == 0 and fail == 0:
        state["offset"] = new_offset
    state["done"] = sorted(done)[-500:]
    _save_state(state)
    print(f"[beacon] Terminé: {ok} sessions indexées, {fail} en échec.")
    return 0 if fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Beacon -> mémoire unifiée Hephaistos")
    ap.add_argument("--once", action="store_true", help="Run unique (défaut)")
    ap.add_argument("--dry-run", action="store_true", help="Aperçu sans écriture")
    ap.add_argument("--limit", type=int, default=MAX_SESSIONS_DEFAULT)
    ap.add_argument("--reset", action="store_true", help="Repartir de zéro")
    ap.add_argument("--log-path", default=None, help="Chemin runtime.jsonl")
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
