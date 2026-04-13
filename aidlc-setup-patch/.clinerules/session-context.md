# ALWAYS-ACTIVE: Session Context Recovery
# This rule applies to ALL interactions, not just AI-DLC workflow sessions

## MANDATORY: First Action on Every New Session
**Before doing ANY work**, read `WORKLOG.md` in the workspace root to recover context from previous sessions.

This applies whether the user is:
- Doing formal AI-DLC software development
- Casually coding, debugging, or tweaking
- Asking questions about the codebase
- Doing any kind of work in this workspace

## What to Do After Reading WORKLOG.md
1. Briefly acknowledge what you learned (1-2 sentences max, don't dump the whole file back)
2. If the user's request relates to something in the worklog, connect the dots
3. If the user asks to "continue" or "pick up where we left off", use the worklog to determine what that means
4. If the worklog seems outdated, mention it and offer to update it

## Deep Context: SQLite Session Memory
For deeper context beyond WORKLOG.md, a SQLite database is available at `.ai-memory/sessions.db`.

**When to query the DB** (use `python3 .ai-memory/ai_memory.py <command>`):
- User asks "what did we decide about X?" → `python3 .ai-memory/ai_memory.py search "X"`
- User asks about past sessions → `python3 .ai-memory/ai_memory.py history`
- User asks about past decisions → `python3 .ai-memory/ai_memory.py decisions`
- User asks about blockers → `python3 .ai-memory/ai_memory.py blockers`
- Need full JSON context → `python3 .ai-memory/ai_memory.py context`

**During a session**, log important events:
- Start: `python3 .ai-memory/ai_memory.py start "Session title"`
- Work done: `python3 .ai-memory/ai_memory.py log "Description"`
- Decisions: `python3 .ai-memory/ai_memory.py decide "Decision" "Rationale"`
- Blockers: `python3 .ai-memory/ai_memory.py blocker "Description"`
- Files: `python3 .ai-memory/ai_memory.py file "path" "action"`

## MANDATORY: End-of-Session Update
When a session is ending (user says goodbye, thanks, or the work is clearly done):
1. **Log session end**: `python3 .ai-memory/ai_memory.py end "Summary of what was done"`
2. **Sync WORKLOG.md**: `python3 .ai-memory/ai_memory.py sync-worklog`
3. **Ask the user**: "Want me to update WORKLOG.md with what we did today?" (if sync-worklog wasn't run)

## What WORKLOG.md Contains
- Project overview and architecture quick reference
- What was worked on last session (auto-generated from DB)
- Current state and where we left off
- Known issues and blockers
- Recent decisions
- Key files to read for deeper context
- Session history log

## Relationship to AI-DLC Workflow
- If the user triggers the AI-DLC workflow (e.g., "build me a feature"), follow `core-workflow.md` as usual
- WORKLOG.md + .ai-memory/ is for **everything else** — the ad-hoc coding, debugging, UI tweaks, data fixes, etc.
- Both systems complement each other; WORKLOG.md fills the gap for non-workflow sessions
