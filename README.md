# Forge — Multi-Agent AI Coding Agent

**Give it a sentence. Get back a working, tested, downloadable project.**

**[Live demo →](https://agentic-coding-agent.onrender.com)** · Built with LangGraph + Groq · 8-node agentic pipeline · Deployed on Render

---

## The Problem

Ask any LLM to write you code and it will — confidently, fluently, and with no guarantee any of it actually runs. A single response is just text: no verification that it executes, no consistency check across multiple files that import from each other, no recovery when it's wrong. The gap between *"an LLM produced code"* and *"the code works"* is left entirely to the person reading it.

## What Forge Does Differently

Forge closes that gap by treating code generation as a sequence of accountable actions, not a single guess:

1. **Plans** the project and asks for explicit human approval before writing a single line — and if the plan is rejected with feedback, it genuinely re-plans rather than patching the rejection onto the old plan
2. **Designs** the file structure and cross-file dependencies up front, so files that import from each other actually stay consistent
3. **Writes** real files to a real folder on disk — not a code block in a chat window
4. **Executes** every file it writes, in an isolated process, to check whether it actually runs
5. **Diagnoses and repairs** its own failures, feeding the real error message back into a correction pass, up to three attempts per file, before giving up honestly
6. **Packages** the finished, verified project into a downloadable archive

Every generated file is labeled **verified** or **generated** based on whether step 4 actually confirmed it works — not on whether the LLM sounded confident.

It's deployed as a web application so anyone can use it end-to-end, while remaining architected as a single-session tool rather than a multi-tenant production service.

**Key capabilities:**
- Multi-agent pipeline with distinct planning, architecture, generation, and verification stages
- Human-in-the-loop plan approval with a full reject-and-revise loop — rejecting sends the request back to the Planner with the requested changes, producing a genuinely revised plan for re-review
- Automated execution of generated code with error-driven retry (up to 3 attempts per file)
- Multi-file projects with consistent cross-file dependencies (shared function names, correct imports)
- Persistent, resumable state via SQLite checkpointing
- Downloadable output as a ready-to-run zip archive
- Deployed and publicly accessible, not just a local script

---

## Architecture

```
                         START
                           │
                    ┌──────▼──────┐
                    │   Planner   │  Scopes the request into a
                    │             │  structured project plan
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌────▶│    HITL     │  Pauses for human approval
              │     │             │  of the plan
              │     └──────┬──────┘
              │             │
              │      approved│rejected
              │             │    │
              │      ┌──────▼──┐ │
              │      │Architect│ └──────────┐
              │      └────┬────┘            │
              │           │           (re-run Planner
              └───────────┘            with the requested
                                        changes, then
                                        pause at HITL again)
                  ┌────────▼────────┐
            ┌────▶│      Coder      │  Writes one file, using
            │     │                 │  already-built dependencies
            │     └────────┬────────┘  as context
            │              │
            │     ┌────────▼────────┐
            │     │    Executor     │  Runs the file as a real
            │     │                 │  subprocess to verify it works
            │     └────────┬────────┘
            │        success│fail (retries remaining)
            │       +more   │
            │       files   │
            │         │     │
            │  ┌──────▼──┐  │  ┌──────────┐
            └──┤move_to_ │  │  │ Packager │  Zips the finished
               │next_file│  │  │          │  project for download
               └─────────┘  │  └──────────┘
                      ┌──────▼──────┐
                      │    Fixer    │  Regenerates the file using
                      │             │  the captured error message
                      └──────┬──────┘
                             │
                             └──────────▶ back to Executor
```

Eight nodes, each with a single responsibility: **Planner** (scope), **HITL** (human checkpoint, with revise-and-re-plan on rejection), **Architect** (design), **Coder** (create), **Executor** (verify), **Fixer** (repair), **move_to_next_file** (advance the build pointer), **Packager** (deliver).

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Orchestration | LangGraph (`StateGraph`) | Branching and looping (retry logic, multi-file progression, plan revision) required a graph, not a linear chain |
| LLMs | Groq — `openai/gpt-oss-120b` (Planner, Architect) + `qwen/qwen3.6-27b` (Coder, Fixer) | Reasoning-heavy nodes use the larger model; high-volume, per-file generation nodes use a faster model to manage rate limits |
| Structured output | Groq native schema-enforced output with Pydantic | Guarantees valid `ProjectPlan` / `ArchitectOutput`; code generation itself is left as raw text, since source code is not structured data |
| Human-in-the-loop | LangGraph `interrupt()` | Prevents wasted generation work on an incorrect plan; supports both approval and a full revise-and-re-plan cycle |
| Checkpointing | SQLite (`SqliteSaver`) | Persists paused graph state so an approval interrupt can be resumed |
| Verification | Python `subprocess` | Executes generated code as an isolated process — the only reliable way to confirm it runs |
| Frontend | Streamlit | Custom-styled, session-isolated multi-stage interface (request → plan approval/revision → results) |
| Packaging | `shutil.make_archive` | Delivers the finished project as a single downloadable archive |

---

## Evaluation

The system was tested end-to-end through the frontend using eight varied natural-language requests spanning different domains and complexity levels. For every generated file, the outcome was recorded as **verified** (executed successfully via the Executor's subprocess run) or **generated** (written successfully but not confirmed executable by automated testing).

| # | Request | Files | Verified | Generated (unverified) |
|---|---|---|---|---|
| 1 | Quiz app that asks questions and scores the user | 1 | 0 | 1 |
| 2 | Command-line prime number checker | 1 | 0 | 1 |
| 3 | Library book tracker with search | 2 | 1 | 1 |
| 4 | Inventory management tool | 2 | 1 | 1 |
| 5 | Student grade management system | 3 | 2 | 1 |
| 6 | Personal finance tracker (with plan revision tested) | 3 | 3 | 0 |
| 7 | Contact book with search (auto-generated test file included) | 4 | 4 | 0 |
| 8 | Recipe manager with favorites (with plan revision tested) | 2 | 1 | 1 |
| **Total** | | **18** | **12** | **6** |

Findings 

Finding 1: **Files with no user interaction always passed on the first try. Files needing input() were correctly written but couldn't be confirmed working — the Executor still checks the file's full syntax, even with input() in it, but can't run the code past that line since nobody's there to type a response.**

Finding 2: When asked to use a specific library (LangGraph) inside the generated code, the Coder agent sometimes ignored it and wrote simpler code instead — and since that simpler code still ran fine, the system had no way to catch that the actual requirement wasn't met.
---

## Limitations

- **Interactive programs are generated but not fully verified.** The Executor syntax-checks the entire file, and executes and confirms all logic up to the first `input()` call — but code after that point cannot run, since the Executor supplies no response to wait on, so its correctness is untested. The same applies to files requiring command-line arguments.
- **Generated pipelines requiring external API calls cannot be meaningfully executed by the Executor as-is** — a generated project that itself calls an LLM API would need real credentials, longer timeouts, and would incur real API cost simply to verify, which the current Executor does not account for.
- **`build_order` is not yet explicitly enforced** in the execution loop, which currently iterates `architecture.files` in list order; for most requests these coincide, but this is a known gap.
- **No guardrails layer** currently screens generated code for unsafe operations before execution.
- **Single-session, local execution.** Generated files are written to local disk ; the system is architected as a personal coding agent with a deployed interface, not a concurrent multi-tenant production service.

---

## Possible Future Improvements
- A more capable execution sandbox supporting piped input
- Explicit enforcement of `build_order` in the execution loop
- A lightweight guardrails check before Coder writes generated code to disk


---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:
```
GROQ_API_KEY=your_key_here
```

Run:
```bash
python -m streamlit run frontend.py
```

---

## Project Structure

```
├── backend.py            # LangGraph nodes, schemas import, and compiled graph
├── frontend.py            # Streamlit interface
├── schemas.py             # Pydantic schemas (ProjectPlan, ArchitectOutput, FileTask, ExecutionResult)
├── requirements.txt
└── generated_projects/   # Output directory (created at runtime)
```
