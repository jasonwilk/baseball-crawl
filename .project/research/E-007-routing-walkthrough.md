# E-007 Routing Scenario Walkthrough

Date: 2026-02-28
Status: APPROVED

## Prerequisite Check

All four implementation stories verified DONE before this walkthrough began:
- E-007-01: CLAUDE.md Workflow Contract section -- DONE
- E-007-02: Orchestrator prompt PM-as-gatekeeper -- DONE
- E-007-03: PM prompt Dispatch Mode -- DONE
- E-007-04: Workflow discipline rules file -- DONE
- E-007-05: Implementing agent Work Authorization -- DONE

## Files Reviewed

1. `/Users/jason/Documents/code/baseball-crawl/.claude/agents/orchestrator.md`
2. `/Users/jason/Documents/code/baseball-crawl/.claude/agents/product-manager.md`
3. `/Users/jason/Documents/code/baseball-crawl/.claude/agents/general-dev.md`
4. `/Users/jason/Documents/code/baseball-crawl/.claude/agents/data-engineer.md`
5. `/Users/jason/Documents/code/baseball-crawl/.claude/rules/workflow-discipline.md`
6. `/Users/jason/Documents/code/baseball-crawl/CLAUDE.md` (Workflow Contract section)

## Scenario Results

| # | Scenario | Expected | Actual | Pass/Fail |
|---|----------|----------|--------|-----------|
| 1 | "Start epic E-001" | Orchestrator -> PM, PM enters Dispatch Mode and dispatches stories | Orchestrator Routing Rule #1 catches "start an epic" -> routes to PM. PM Dispatch Mode trigger matches "Start epic E-001" -> PM reads epic, identifies TODO stories, dispatches each with full context block. | PASS |
| 2 | "Write the credential parser" | Orchestrator -> PM (no direct dev routing) | Orchestrator Rule #1: "implement a feature...build a component" covers "write the...parser" -> routes to PM. PM in Planning Mode reviews whether a story exists before authorizing any implementation. Does NOT route to general-dev directly. | PASS |
| 3 | "Explore the GameChanger teams endpoint" | Orchestrator -> api-scout direct | Orchestrator Direct-Routing Exceptions: "api-scout: Exploratory API work, endpoint discovery, credential management" -- matches exactly. Routes directly, no PM intermediation. | PASS |
| 4 | "What batting stats do coaches care about?" | Orchestrator -> baseball-coach direct | Orchestrator Direct-Routing Exceptions: "baseball-coach: Domain consultation, coaching requirements, stat validation" -- matches. Routes directly, no PM intermediation. | PASS |
| 5 | "Add a new code review agent" | Orchestrator -> claude-architect direct | Orchestrator Direct-Routing Exceptions: "claude-architect: Agent infrastructure, CLAUDE.md design, rules, skills" -- agent creation is explicitly listed. Routes directly, no PM intermediation. | PASS |
| 6 | general-dev receives task with no story reference | general-dev refuses, names what is missing | general-dev Work Authorization: "If no story reference is found in the task prompt, DO NOT begin implementation. Instead, respond: 'I need a story file reference before beginning implementation. Please provide the story ID (e.g., E-001-02) or the path to the story file.'" -- exact refusal behavior present. | PASS |
| 7 | data-engineer receives task with story ID "E-003-01" | data-engineer proceeds, reads story, begins implementation | data-engineer Work Authorization: story ID `E-003-01` is an acceptable reference format ("Story ID: e.g., `E-003-01`"). "Once you have a story reference, read the story file in full before writing any SQL or code." -- proceeds to implement. | PASS |
| 8 | PM dispatches E-001-01 to general-dev | PM sends full context block (story path + contents + epic Technical Notes + dependency statuses) | PM Dispatch Mode Standard Context Block requires all four elements: (a) absolute story file path, (b) full story contents, (c) epic Technical Notes, (d) dependency statuses. general-dev Work Authorization validates the story reference and proceeds. | PASS |

## Gaps Found

None. All eight scenarios produce the correct routing and behavior as specified in the updated agent prompts and rules files.

The language in each file is specific enough to correctly classify every test case without ambiguity:
- "Start an epic" in the orchestrator rule unambiguously catches scenario 1
- "Implement a feature, build a component" catches scenario 2 (writing a parser = implementing a feature)
- The three direct-routing exceptions are named explicitly, covering scenarios 3-5
- The work authorization refusal message in general-dev and data-engineer is identical and covers scenarios 6-8

## Resolution

No gaps to resolve. All scenarios pass on first review.

## Sign-Off

Reviewed by: product-manager (PM Dispatch Mode, acting as coordination hub for E-007)
Date: 2026-02-28
APPROVED
