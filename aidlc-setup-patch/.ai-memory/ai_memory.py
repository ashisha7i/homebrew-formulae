#!/usr/bin/env python3
"""
AI Session Memory — SQLite-backed session history for AI coding assistants.

Usage:
    python .ai-memory/ai_memory.py init                          # Create/reset DB
    python .ai-memory/ai_memory.py start "Working on dashboard"  # Start a session
    python .ai-memory/ai_memory.py log "Fixed the tooltip bug"   # Log work item
    python .ai-memory/ai_memory.py decide "Use D3 over Recharts" "Better SVG control"
    python .ai-memory/ai_memory.py blocker "Redis not starting"
    python .ai-memory/ai_memory.py resolve 1                     # Resolve blocker by ID
    python .ai-memory/ai_memory.py file "src/components/Chart.tsx" "Refactored"
    python .ai-memory/ai_memory.py end "Completed tooltip fix"   # End session
    python .ai-memory/ai_memory.py context                       # Get context for AI (JSON)
    python .ai-memory/ai_memory.py search "radial chart"         # Search all history
    python .ai-memory/ai_memory.py history                       # Show recent sessions
    python .ai-memory/ai_memory.py decisions                     # Show all decisions
    python .ai-memory/ai_memory.py blockers                      # Show open blockers
    python .ai-memory/ai_memory.py sync-worklog                  # Update WORKLOG.md from DB
"""

import sqlite3
import sys
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.db")
WORKLOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "WORKLOG.md")


def get_db():
    """Get a database connection, auto-initializing schema if needed."""
    needs_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if needs_init:
        _create_schema(conn)
    return conn


def _create_schema(conn):
    """Create database tables (idempotent — safe to call multiple times)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            ended_at TEXT,
            title TEXT NOT NULL,
            summary TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS work_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            description TEXT NOT NULL,
            category TEXT DEFAULT 'general'
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            decision TEXT NOT NULL,
            rationale TEXT,
            tags TEXT
        );
        CREATE TABLE IF NOT EXISTS files_touched (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            file_path TEXT NOT NULL,
            action TEXT DEFAULT 'modified',
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS blockers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            resolved_at TEXT,
            description TEXT NOT NULL,
            resolution TEXT,
            status TEXT NOT NULL DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS project_context (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_work_items_session ON work_items(session_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);
        CREATE INDEX IF NOT EXISTS idx_files_session ON files_touched(session_id);
        CREATE INDEX IF NOT EXISTS idx_blockers_status ON blockers(status);
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, source_type, source_id
        );
    """)
    conn.commit()


def init_db():
    """Explicitly create/reset the database schema."""
    conn = get_db()
    _create_schema(conn)
    print("✅ Database initialized at", DB_PATH)
    conn.close()


def get_active_session(conn):
    """Get the current active session, or None."""
    row = conn.execute(
        "SELECT * FROM sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row


def start_session(title):
    conn = get_db()
    # End any active sessions first
    conn.execute(
        "UPDATE sessions SET status = 'completed', ended_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE status = 'active'"
    )
    cursor = conn.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
    session_id = cursor.lastrowid
    conn.commit()
    print(f"✅ Session #{session_id} started: {title}")
    conn.close()
    return session_id


def log_work(description, category="general"):
    conn = get_db()
    session = get_active_session(conn)
    if not session:
        print("⚠️  No active session. Starting one...")
        conn.close()
        start_session("Ad-hoc work")
        conn = get_db()
        session = get_active_session(conn)

    conn.execute(
        "INSERT INTO work_items (session_id, description, category) VALUES (?, ?, ?)",
        (session["id"], description, category),
    )
    # Also add to FTS
    conn.execute(
        "INSERT INTO memory_fts (content, source_type, source_id) VALUES (?, 'work', last_insert_rowid())",
        (description,),
    )
    conn.commit()
    print(f"📝 Logged: {description}")
    conn.close()


def log_decision(decision, rationale=None, tags=None):
    conn = get_db()
    session = get_active_session(conn)
    if not session:
        print("⚠️  No active session.")
        conn.close()
        return

    conn.execute(
        "INSERT INTO decisions (session_id, decision, rationale, tags) VALUES (?, ?, ?, ?)",
        (session["id"], decision, rationale, tags),
    )
    conn.execute(
        "INSERT INTO memory_fts (content, source_type, source_id) VALUES (?, 'decision', last_insert_rowid())",
        (f"{decision} {rationale or ''}",),
    )
    conn.commit()
    print(f"🔨 Decision logged: {decision}")
    conn.close()


def log_blocker(description):
    conn = get_db()
    session = get_active_session(conn)
    if not session:
        print("⚠️  No active session.")
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO blockers (session_id, description) VALUES (?, ?)",
        (session["id"], description),
    )
    blocker_id = cursor.lastrowid
    conn.commit()
    print(f"🚫 Blocker #{blocker_id}: {description}")
    conn.close()


def resolve_blocker(blocker_id, resolution="Resolved"):
    conn = get_db()
    conn.execute(
        "UPDATE blockers SET status = 'resolved', resolution = ?, resolved_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
        (resolution, blocker_id),
    )
    conn.commit()
    print(f"✅ Blocker #{blocker_id} resolved")
    conn.close()


def log_file(file_path, action="modified", notes=None):
    conn = get_db()
    session = get_active_session(conn)
    if not session:
        print("⚠️  No active session.")
        conn.close()
        return

    conn.execute(
        "INSERT INTO files_touched (session_id, file_path, action, notes) VALUES (?, ?, ?, ?)",
        (session["id"], file_path, action, notes),
    )
    conn.commit()
    print(f"📄 {action}: {file_path}")
    conn.close()


def end_session(summary=None):
    conn = get_db()
    session = get_active_session(conn)
    if not session:
        print("⚠️  No active session to end.")
        conn.close()
        return

    conn.execute(
        "UPDATE sessions SET status = 'completed', summary = ?, ended_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
        (summary, session["id"]),
    )
    conn.commit()
    print(f"✅ Session #{session['id']} ended: {summary or session['title']}")
    conn.close()


def get_context():
    """Get full context for AI assistant — outputs JSON."""
    conn = get_db()

    # Last 3 sessions
    sessions = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT 3"
    ).fetchall()

    # Open blockers
    blockers = conn.execute(
        "SELECT * FROM blockers WHERE status = 'open' ORDER BY created_at DESC"
    ).fetchall()

    # Recent decisions (last 10)
    decisions = conn.execute(
        "SELECT d.*, s.title as session_title FROM decisions d JOIN sessions s ON d.session_id = s.id ORDER BY d.created_at DESC LIMIT 10"
    ).fetchall()

    # Recent work items from last session
    last_session = sessions[0] if sessions else None
    work_items = []
    files = []
    if last_session:
        work_items = conn.execute(
            "SELECT * FROM work_items WHERE session_id = ? ORDER BY created_at",
            (last_session["id"],),
        ).fetchall()
        files = conn.execute(
            "SELECT * FROM files_touched WHERE session_id = ? ORDER BY id",
            (last_session["id"],),
        ).fetchall()

    context = {
        "last_session": {
            "id": last_session["id"] if last_session else None,
            "title": last_session["title"] if last_session else None,
            "status": last_session["status"] if last_session else None,
            "started_at": last_session["started_at"] if last_session else None,
            "ended_at": last_session["ended_at"] if last_session else None,
            "summary": last_session["summary"] if last_session else None,
            "work_items": [dict(w) for w in work_items],
            "files_touched": [dict(f) for f in files],
        } if last_session else None,
        "recent_sessions": [
            {"id": s["id"], "title": s["title"], "started_at": s["started_at"], "status": s["status"]}
            for s in sessions
        ],
        "open_blockers": [
            {"id": b["id"], "description": b["description"], "created_at": b["created_at"]}
            for b in blockers
        ],
        "recent_decisions": [
            {"decision": d["decision"], "rationale": d["rationale"], "session": d["session_title"], "date": d["created_at"]}
            for d in decisions
        ],
    }

    print(json.dumps(context, indent=2))
    conn.close()
    return context


def search_memory(query):
    """Full-text search across all session history."""
    conn = get_db()

    # Search FTS
    results = conn.execute(
        "SELECT content, source_type, source_id FROM memory_fts WHERE memory_fts MATCH ? ORDER BY rank LIMIT 20",
        (query,),
    ).fetchall()

    # Also search sessions, decisions, work items directly for broader matches
    like_query = f"%{query}%"

    sessions = conn.execute(
        "SELECT id, title, summary, started_at FROM sessions WHERE title LIKE ? OR summary LIKE ? ORDER BY started_at DESC LIMIT 5",
        (like_query, like_query),
    ).fetchall()

    decisions = conn.execute(
        "SELECT decision, rationale, created_at FROM decisions WHERE decision LIKE ? OR rationale LIKE ? ORDER BY created_at DESC LIMIT 10",
        (like_query, like_query),
    ).fetchall()

    work_items = conn.execute(
        "SELECT description, category, created_at FROM work_items WHERE description LIKE ? ORDER BY created_at DESC LIMIT 10",
        (like_query,),
    ).fetchall()

    output = {
        "query": query,
        "fts_results": [{"content": r["content"], "type": r["source_type"]} for r in results],
        "matching_sessions": [dict(s) for s in sessions],
        "matching_decisions": [dict(d) for d in decisions],
        "matching_work_items": [dict(w) for w in work_items],
    }

    print(json.dumps(output, indent=2))
    conn.close()


def show_history(limit=10):
    """Show recent session history."""
    conn = get_db()
    sessions = conn.execute(
        "SELECT s.*, COUNT(w.id) as work_count FROM sessions s LEFT JOIN work_items w ON w.session_id = s.id GROUP BY s.id ORDER BY s.started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    for s in sessions:
        status_icon = "🟢" if s["status"] == "active" else "✅"
        print(f"{status_icon} #{s['id']} [{s['started_at'][:10]}] {s['title']} ({s['work_count']} items)")
        if s["summary"]:
            print(f"   Summary: {s['summary']}")

    conn.close()


def show_decisions():
    """Show all decisions."""
    conn = get_db()
    decisions = conn.execute(
        "SELECT d.*, s.title as session_title FROM decisions d JOIN sessions s ON d.session_id = s.id ORDER BY d.created_at DESC"
    ).fetchall()

    for d in decisions:
        print(f"🔨 [{d['created_at'][:10]}] {d['decision']}")
        if d["rationale"]:
            print(f"   Why: {d['rationale']}")
        print(f"   Session: {d['session_title']}")
        print()

    conn.close()


def show_blockers():
    """Show open blockers."""
    conn = get_db()
    blockers = conn.execute(
        "SELECT b.*, s.title as session_title FROM blockers b JOIN sessions s ON b.session_id = s.id WHERE b.status = 'open' ORDER BY b.created_at DESC"
    ).fetchall()

    if not blockers:
        print("✅ No open blockers!")
        return

    for b in blockers:
        print(f"🚫 #{b['id']} [{b['created_at'][:10]}] {b['description']}")
        print(f"   From session: {b['session_title']}")

    conn.close()


def sync_worklog():
    """Generate WORKLOG.md from the database."""
    conn = get_db()

    # Get last session
    last_session = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not last_session:
        print("⚠️  No sessions to sync.")
        conn.close()
        return

    # Get work items for last session
    work_items = conn.execute(
        "SELECT * FROM work_items WHERE session_id = ? ORDER BY created_at",
        (last_session["id"],),
    ).fetchall()

    # Get open blockers
    blockers = conn.execute(
        "SELECT * FROM blockers WHERE status = 'open'"
    ).fetchall()

    # Get recent sessions for history
    recent = conn.execute(
        "SELECT s.*, GROUP_CONCAT(w.description, '; ') as items FROM sessions s LEFT JOIN work_items w ON w.session_id = s.id GROUP BY s.id ORDER BY s.started_at DESC LIMIT 10"
    ).fetchall()

    # Get recent decisions
    decisions = conn.execute(
        "SELECT * FROM decisions ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    # Build WORKLOG.md
    lines = [
        "# Work Log — Session Context for AI Assistant\n",
        "> **Purpose**: This file is auto-generated from `.ai-memory/sessions.db`.",
        "> Run `python .ai-memory/ai_memory.py sync-worklog` to refresh.\n",
        "---\n",
        "## Project Overview",
        "- **Name**: Code Effectiveness Platform (ai_eff)",
        "- **Repo**: https://github.com/MGMResorts/ai_eff.git",
        "- **Stack**: Python (FastAPI) backend services + Next.js (TypeScript) dashboard",
        "- **Infra**: Docker Compose (PostgreSQL, Redis, metrics-engine, observer-agent, dashboard)",
        "- **Monorepo root**: `aidlc-platform/`\n",
        "## Current Active Work\n",
        f"**Last Session**: {last_session['started_at'][:10]}",
        f"**Title**: {last_session['title']}",
        f"**Status**: {last_session['status']}\n",
        "**What we worked on**:",
    ]

    for w in work_items:
        lines.append(f"- {w['description']}")

    if not work_items:
        lines.append("- (no items logged)")

    lines.append(f"\n**Summary**: {last_session['summary'] or '(session still active)'}\n")

    # Blockers
    lines.append("**Known issues / blockers**:")
    if blockers:
        for b in blockers:
            lines.append(f"- 🚫 #{b['id']}: {b['description']}")
    else:
        lines.append("- ✅ No open blockers")

    # Recent decisions
    lines.append("\n## Recent Decisions\n")
    if decisions:
        for d in decisions:
            lines.append(f"- **{d['decision']}** — {d['rationale'] or 'no rationale recorded'} ({d['created_at'][:10]})")
    else:
        lines.append("- (no decisions recorded yet)")

    # Session history
    lines.append("\n---\n")
    lines.append("## Session History\n")
    for s in recent:
        status_icon = "🟢" if s["status"] == "active" else "✅"
        lines.append(f"### {status_icon} {s['started_at'][:10]} — {s['title']}")
        if s["items"]:
            for item in s["items"].split("; "):
                lines.append(f"- {item}")
        if s["summary"]:
            lines.append(f"- **Summary**: {s['summary']}")
        lines.append("")

    # Key files table
    lines.extend([
        "---\n",
        "## Key Files to Read for Context",
        "| Area | File | What it tells you |",
        "|------|------|-------------------|",
        "| Overall state | `aidlc-docs/aidlc-state.md` | AI-DLC workflow progress |",
        "| Architecture | `aidlc-docs/inception/application-design/components.md` | All system components |",
        "| Requirements | `aidlc-docs/inception/requirements/requirements.md` | What we're building |",
        "| Dashboard plan | `aidlc-platform/dashboard/V2-EXECUTIVE-DASHBOARD-PLAN.md` | V2 dashboard design |",
        "| DB models | `aidlc-platform/core-data/core_data/models.py` | All database tables |",
        "| API endpoints | `aidlc-platform/metrics-engine/metrics_engine/main.py` | All REST endpoints |",
        "| Docker setup | `aidlc-platform/docker-compose.yml` | How to run everything |",
        "| Session memory | `.ai-memory/sessions.db` | Full queryable session history |",
    ])

    worklog_content = "\n".join(lines) + "\n"

    with open(WORKLOG_PATH, "w") as f:
        f.write(worklog_content)

    print(f"✅ WORKLOG.md synced from database ({len(recent)} sessions)")
    conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "init":
        init_db()
    elif cmd == "start":
        title = sys.argv[2] if len(sys.argv) > 2 else "Untitled session"
        start_session(title)
    elif cmd == "log":
        desc = sys.argv[2] if len(sys.argv) > 2 else "Work done"
        cat = sys.argv[3] if len(sys.argv) > 3 else "general"
        log_work(desc, cat)
    elif cmd == "decide":
        decision = sys.argv[2] if len(sys.argv) > 2 else "Decision"
        rationale = sys.argv[3] if len(sys.argv) > 3 else None
        tags = sys.argv[4] if len(sys.argv) > 4 else None
        log_decision(decision, rationale, tags)
    elif cmd == "blocker":
        desc = sys.argv[2] if len(sys.argv) > 2 else "Unknown blocker"
        log_blocker(desc)
    elif cmd == "resolve":
        bid = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        res = sys.argv[3] if len(sys.argv) > 3 else "Resolved"
        resolve_blocker(bid, res)
    elif cmd == "file":
        path = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        action = sys.argv[3] if len(sys.argv) > 3 else "modified"
        notes = sys.argv[4] if len(sys.argv) > 4 else None
        log_file(path, action, notes)
    elif cmd == "end":
        summary = sys.argv[2] if len(sys.argv) > 2 else None
        end_session(summary)
    elif cmd == "context":
        get_context()
    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        search_memory(query)
    elif cmd == "history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_history(limit)
    elif cmd == "decisions":
        show_decisions()
    elif cmd == "blockers":
        show_blockers()
    elif cmd == "sync-worklog":
        sync_worklog()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
