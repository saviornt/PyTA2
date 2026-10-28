---
name: pyta-sprint
description: How to start, run and close a PyTA sprint by the rules in docs/DEVELOPMENT.md, with TODO.md as the working plan - confirming the goal and acceptance criteria, ticking tasks only when verified, keeping docs and memory current, adding an inserted sprint (such as 7.5), writing the retrospective and marking a sprint complete. Use this whenever the user says to start, continue, plan, review or finish a sprint, asks what is left in the current sprint, refers to TODO.md items or sprint tasks, or asks to add or revise a sprint.
---

# Running a PyTA sprint

`docs/DEVELOPMENT.md` is the plan of record: every sprint has a **Goal**, **Tasks** (checkboxes), **Acceptance criteria**, a **Retrospective** line and a **Sprint completion** marker (`☐` or `✓`). Its "Sprint tracking rules" section is binding; read it at the start of any sprint work. `TODO.md` is the working scratchpad for the current sprint: the detailed plan in parts, its own acceptance criteria and verification list, what is out of scope, and a parking lot.

Find the current sprint: the first one in `DEVELOPMENT.md` whose marker is `☐`, unless `TODO.md` plans an inserted sprint (for example 7.5) that comes before it.

## Starting a sprint

1. Read the sprint in `DEVELOPMENT.md`, its plan in `TODO.md` if there is one, and `.claude/memory.md` (decisions that constrain it).
2. **Confirm the goal and acceptance criteria with the user** before working (tracking rule 1). Point out anything that conflicts with the code as it is now, or with a recorded decision.
3. If `TODO.md` has no plan for it, draft one in the same shape as the existing plans (parts with checkboxes and rough sizes, acceptance criteria, verification, out of scope) and agree it with the user.
4. Keep pieces small enough to review and test on their own (rule 2). Do the parts in order unless the plan says otherwise.

## During the sprint

- **Tick a box only when its deliverable is finished and verified** (rule 3): code written and its tests passing, not "implemented". Tick it in `TODO.md`, and in `DEVELOPMENT.md` when it is one of the sprint's own tasks.
- **Verification means evidence:** a test-suite report (`pyta-testing` skill), a benchmark report (`pyta-benchmarks` skill), or a named manual check. Mention the report file when ticking something that depends on it.
- **An architectural problem comes first** (rule 6): stop adding features, tell the user, and fix the foundation as part of the sprint or a new task.
- **Docs in the same change** (rule 8): `ARCHITECTURE.md` and `API.md` with the code that alters them, `scripts/README.md` with script changes.
- **Decisions** that the code and docs will not show go in `.claude/memory.md` (Decisions or Lessons), dated; remove entries that stop being true.
- **New ideas** that are not part of the sprint go in the `TODO.md` parking lot, not into the work.
- **Indicators** are added with the `add-indicator` skill.
- Commit only on worktree branches, never on `main`; never push. The maintainer reviews, merges into `main` locally and pushes.

## Adding or revising a sprint

- An inserted sprint gets a decimal number (Sprint 7.5) and goes between its neighbours in `DEVELOPMENT.md`, with the same structure: `## Sprint N — Title`, `**Goal:**`, `### Tasks`, `### Acceptance criteria`, `**Retrospective:**`, `**Sprint completion:** ☐`.
- Revising a later sprint (for example to match a new decision) changes its tasks and criteria only; keep its number and its `☐`.
- Tell the user what changed in the plan, since `DEVELOPMENT.md` is a tracked file.

## Closing a sprint

1. Run the full checks: `./scripts/test-suite.sh` always, and the benchmarks the sprint's criteria name (or `--single --python` and `--batch --python` if the sprint touched hot paths).
2. Go through **every acceptance criterion** and give the evidence for each: report file, test name, or manual check. List any that are not met.
3. Fill the **Retrospective** line (rule 7), in one or two sentences each: what worked, what did not, and the next sprint's priorities. Draft it and let the user adjust it.
4. **Mark `✓` only after every acceptance criterion passes** (rule 5), and only once the user agrees. Until then the marker stays `☐`, even if every task box is ticked.
5. Update `TODO.md`: summarise what is still open, keep the parking lot, and ask before deleting the finished plan or replacing it with the next sprint's.
6. Check `.claude/memory.md` and the `pyta-tooling` skill still describe the project as it now is.
