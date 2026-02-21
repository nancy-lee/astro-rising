---
name: wrap
description: End session — save a session log and update memory
argument-hint: [optional: notes to remember]
---

# /wrap — Session Wrap-up

Save session context so we can pick up where we left off next time.

## Steps

1. **Review what was done this session**
   - Check git log for commits: !`git log --oneline -10`
   - Check for uncommitted changes: !`git status --short`
   - Note significant work, decisions, and discoveries

2. **Create a session log** in `.claude/sessions/`
   - Filename: `YYYY-MM-DD.md` (if today's file exists, append `-2`, `-3`, etc.)
   - Template:
     ```
     # Session — YYYY-MM-DD

     ## What was done
     - (bullet points of work completed)

     ## Decisions
     - (decisions made and why)

     ## Open threads
     - (anything unresolved or worth noting next time)
     ```

3. **Update auto memory** at `~/.claude/projects/-Users-nancy-Developer-astro-rising/memory/MEMORY.md`
   - Add any stable patterns or conventions confirmed this session
   - Note user preferences discovered
   - Remove anything that turned out to be wrong
   - Keep it concise — this goes into the system prompt

4. **Check for loose ends**
   - Uncommitted changes that should be committed?
   - Open questions for next session?

5. **Summarize to the user** — brief recap of what was done and what's next

$ARGUMENTS
