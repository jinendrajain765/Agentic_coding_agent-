# Agentic_coding_agent-

# Forge — Multi-Agent AI Code Generation System
 
A LangGraph-based multi-agent system that converts a natural language request into a complete, working software project — planning the architecture, writing each file, executing it to verify correctness, and automatically self-correcting on failure.
 
**Live demo:** Streamlit frontend with human-in-the-loop plan approval and downloadable project output.
 
---
 
## Overview
 
Forge takes a request such as *"build a command-line student grade management system"* and produces a real, multi-file, working project rather than a single unverified code block. It closes the gap between "an LLM generates code" and "the code actually runs" by pairing generation with automated execution and a bounded self-correction loop.
 
**Key capabilities:**
- Multi-agent pipeline with distinct planning, architecture, generation, and verification stages
- Human-in-the-loop approval of the project plan before any code is generated
- Automated execution of generated code with error-driven retry (up to 3 attempts per file)
- Multi-file projects with consistent cross-file dependencies (shared function names, correct imports)
- Persistent, resumable state via SQLite checkpointing
- Downloadable output as a ready-to-run zip archive
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
                    │    HITL     │  Pauses for human approval
                    │             │  before code generation begins
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Architect  │  Breaks the plan into a
                    │             │  file-by-file build plan
                    └──────┬──────┘
                           │
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
 
Seven nodes, each with a single responsibility: **Planner** (scope), **HITL** (human checkpoint), **Architect** (design), **Coder** (create), **Executor** (verify), **Fixer** (repair), **Packager** (deliver).
 
---
 
## Tech Stack
 
| Layer | Choice | Rationale |
|---|---|---|
| Orchestration | LangGraph (`StateGraph`) | Branching and looping (retry logic, multi-file progression) required a graph, not a linear chain |
| LLMs | Groq — `openai/gpt-oss-120b` (Planner, Architect) + `qwen/qwen3.6-27b` (Coder, Fixer) | Reasoning-heavy nodes use the larger model; high-volume, per-file generation nodes use a faster model to manage rate limits |
| Structured output | Groq native schema-enforced output with Pydantic | Guarantees valid `ProjectPlan` / `ArchitectOutput`; code generation is left as raw text, since source code is not structured data |
| Human-in-the-loop | LangGraph `interrupt()` | Prevents wasted generation work if the initial plan is incorrect |
| Checkpointing | SQLite (`SqliteSaver`) | Persists paused graph state so an approval interrupt can be resumed |
| Verification | Python `subprocess` | Executes generated code as an isolated process — the only reliable way to confirm it runs |
| Frontend | Streamlit | Custom-styled, session-isolated multi-stage interface (request → plan approval → results) |
| Packaging | `shutil.make_archive` | Delivers the finished project as a single downloadable archive |
 
---
 
## Evaluation
 
The system was tested end-to-end through the frontend using five varied natural-language requests spanning different domains and complexity levels (one to three files each). For every generated file, the outcome was recorded as **verified** (executed successfully via the Executor's subprocess run) or **generated** (written successfully but not confirmed executable by automated testing).
 
| # | Request | Files | Verified | Generated (unverified) |
|---|---|---|---|---|
| 1 | Quiz app that asks questions and scores the user | 1 | 0 | 1 |
| 2 | Command-line prime number checker | 1 | 0 | 1 |
| 3 | Library book tracker with search | 2 | 1 | 1 |
| 4 | Inventory management tool | 2 | 1 | 1 |
| 5 | Student grade management system | 3 | 2 | 1 |
| **Total** | | **9** | **4** | **5** |
 
**Finding:** every file with no interactive input (pure logic, storage, or configuration modules) verified successfully on the first attempt, with zero retries required. Every file requiring an interactive CLI menu (`input()`) was correctly generated but not verified — a consistent, single-cause result rather than inconsistent failure: the Executor runs generated files non-interactively, so any file waiting on user input times out with no one present to respond. In each case, the underlying code was confirmed correct when run interactively. See **Limitations** below.
 
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
├── backend.py            # LangGraph nodes, schemas, and compiled graph
├── frontend.py            # Streamlit interface
├── requirements.txt
└── generated_projects/    # Output directory (created at runtime)
```
