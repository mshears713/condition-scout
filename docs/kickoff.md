# Stage 3 Kickoff Prompt — Condition Scout (run record)

Committed verbatim at Milestone 0 per the Implementation procedure
(Run Bindings Rule: run-specific facts live here, not in the Engineering Plan).

---

You are Claude Code acting as the Implementation Engineer for Stage 3 of Mike's AI Planned Personal Software Tool workflow.

RUN BINDINGS — the only facts this prompt adds; all intent lives in Notion:
- Tool: Condition Scout — Van Radar Photo Evidence Tool
- Tool page: https://app.notion.com/p/399850a911d381199117e6963c3df82e
- Implementation repo: https://github.com/mshears713/condition-scout — this exact repo. If you discover other repos with similar names, do not clone, switch to, or write to them; note the finding and stay here.
- Feature branch: create from main
- Notion access for this run: MCP
- Environment notes: Windows 11 + PowerShell, Python via uv. GEMINI_API_KEY exists ONLY as a GitHub Actions repository secret, injected at CI runtime — you will never have it locally; never request, print, log, or commit it. Build the two-job CI split per the Engineering Plan: the fully-faked main suite (no secrets) plus the quota-tiny live-smoke job (`pytest -m live`, <10 requests) that uses the injected secret. Trigger the live-smoke workflow and record its result; if you cannot observe Actions results, record the trigger and defer with a written Stage 4 step. If the secret is absent, the live job must skip cleanly and the affected Ledger items revert to Deferred — a finding, not a stop. Copy the two prompt files from the "Condition Scout — Analysis Prompt Spec" Knowledge page (linked from the Engineering Plan) into prompts/ at M0.

PROCESS:
1. Read, in order: the Tool page (Project Brief, Engineering Plan including any stage addenda and the Validation Ledger); the procedure "Implementation — Personal Software Tool"; the agent "Implementation Engineer"; "Engineering Method Selection & Test Architecture Guide"; "Preferred Agent Harness & MCP Stack"; "Michael Shears — Working Profile & AI Collaboration Guide".
2. Before writing any code, post a short summary of understanding: what the tool is, what Stage 3 must produce, the v0 scope, which Validation Ledger items are Agent-Provable vs Deferred, and any conflict or ambiguity you found. If a true stop condition per the procedure exists, stop and ask; otherwise proceed autonomously — do not wait for approval on the summary or on milestones.
3. In Milestone 0, commit this filled prompt verbatim as docs/kickoff.md (the kickoff record).
4. Execute the Implementation procedure as written in Notion, including the ENTIRE Validation Strategy on the Tool page — every layer that is agent-provable (e.g. AI-readability tests), not only per-milestone checks. If this prompt and Notion ever conflict, Notion wins; flag the conflict in the Build Log.
5. Run-specific facts inside the Engineering Plan's Agent Harness Specification (named agent, OS, repo) are superseded by the Run Bindings above. Treat mismatches as findings to log, not stop conditions.
6. Exit per the procedure: complete Validation Ledger (every item Verified with evidence or Deferred with a written Stage 4 step), Build Log + AVB Report posted to the Tool page's Build Log section (create that section directly after the Engineering Plan section if the template lacks it — never append a duplicate section), a single draft AVB handoff PR, and the Stage 4 Kickoff Prompt generated from its template page (filled from the final Ledger and AVB Report), committed as docs/kickoff-stage4.md and linked in the Build Log.

---

Run-time notes (recorded at M0, not part of the original prompt):
- Actual execution environment: Claude Code remote (managed Linux container),
  not Windows 11 + PowerShell. Logged as a finding per the Run Bindings Rule;
  code is kept Windows-compatible and clean-checkout validation on Windows is
  a Stage 4 step.
