---
name: convert-notebook-ipynb-to-python-project
description: "Use this skill when the user wants to convert a Jupyter notebook (.ipynb) into a standalone, production-quality Python project. Triggers include: 'convert this notebook', 'turn this notebook into a project', 'make this .ipynb a Python app', or any request involving an uploaded .ipynb file (and optionally accompanying dataset files like CSVs) that should become a self-contained, runnable, GitHub-ready folder with modular scripts, requirements, README, and .gitignore. Do NOT use for converting notebooks into slides, reports, or documentation-only output — this skill is specifically for producing runnable Python code."
---

# SKILL: convert-notebook-ipynb-to-python-project

Transform an uploaded Jupyter notebook (`.ipynb`), plus any accompanying data
files, into a clean, modular, self-contained Python project the user can run
from the VS Code terminal on Mac. Follow these phases in strict order. Never
skip a phase gate.

---

## PHASE 0 — INTAKE CHECK
*(Do this before anything else)*

- Confirm at least one `.ipynb` file is present. If not, ask for it — do not
  guess or proceed on a description alone.
- Identify all accompanying files (CSVs, JSON, images, config files, other
  data the notebook reads from disk). If the notebook references a file path
  that isn't among the uploads, flag it explicitly rather than assuming.
- If multiple notebooks are uploaded, ask whether they form one project
  (e.g. separate pipeline stages) or are independent conversions, unless
  this is already obvious from context.

---

## PHASE 1 — EXPLORE & UNDERSTAND
*(Do not write any code in this phase)*

### Read the notebook properly, not just top-to-bottom
- Parse actual cell **execution_count** order, not just file order — notebooks
  are frequently run out of sequence during authoring. If execution order is
  ambiguous or inconsistent (e.g. missing counts, re-run cells), flag it and
  state the logical order you infer.
- Identify and separately catalog:
  1. **Import cells** — the real dependency list (don't guess packages;
     read every `import`/`from` statement, including ones buried mid-notebook)
  2. **Magic commands** (`%matplotlib inline`, `%%time`, `!pip install ...`,
     `%load_ext`, etc.) — these do not translate directly to `.py` files and
     must be converted (see Phase 3)
  3. **Hardcoded values** — file paths, API keys, tokens, credentials, or
     absolute paths (e.g. `/Users/name/Desktop/data.csv`). Flag every
     hardcoded secret explicitly. **Never carry a real secret into the new
     project's source code** — it belongs in `.env`.
  4. **Data I/O** — every place the notebook reads or writes a file, and
     whether the referenced file was actually provided
  5. **Interactive/display-only output** — `display()`, bare trailing
     expressions, inline plots, `df.head()` calls used only for inspection —
     these need a decision (log it, save it, or drop it) rather than a
     literal translation
  6. **Stateful cross-cell dependencies** — variables defined in one cell and
     mutated in another out of function scope; these need to become explicit
     function parameters/returns in the rewritten code

### Detect and report
1. **Python version** — check for a `.python-version`, `environment.yml`,
   `requirements.txt`, or kernel metadata in the notebook's JSON
   (`metadata.kernelspec` / `language_info`). If none found, default to
   Python 3.12 and say so.
2. **Logical project structure** the notebook implies (e.g. data loading →
   preprocessing → model/analysis → evaluation → output) — this becomes the
   module breakdown in Phase 2, not one giant script.
3. **External services or APIs** referenced (OpenAI, AWS, Azure, a REST API,
   a database) — flag credentials each will require.
4. **Gaps or broken cells** — any cell that would error if run today (missing
   file, deprecated API, undefined variable) — flag, don't silently fix
   without calling it out.
5. **Recommended project folder name** (descriptive, tech-stack-first where
   relevant, e.g. `Notebook-CustomerChurn-Analysis`, `NB-SalesForecast-Model`)

---

## PHASE 2 — PLAN & AWAIT APPROVAL
*(Present the plan. Write zero code until the user explicitly approves.)*

### Module breakdown (not a single dumped script)
Propose a folder structure that separates concerns, e.g.:
```
project_name/
├── src/
│   ├── data_loading.py
│   ├── preprocessing.py
│   ├── analysis.py / model.py
│   ├── visualization.py   (if plots exist — saved to /outputs, not inline)
│   └── main.py             (orchestrates the pipeline end to end)
├── data/                   (or reference to where the user's CSV goes)
├── outputs/                (saved plots, results, artifacts)
├── tests/
│   └── test_smoke.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── CHANGELOG.md
```
Adjust the breakdown to fit what the notebook actually does — don't force a
template that doesn't match the content.

### Rules for the rewrite
- **Preserve the original logic exactly.** Do not "improve" model choices,
  hyperparameters, or algorithms unless the user explicitly asked for that —
  this is a conversion task, not a redesign.
- Convert magic commands and notebook-only constructs to real equivalents:
  - `!pip install x` → goes into `requirements.txt`, not runtime code
  - `%matplotlib inline` / inline plots → `matplotlib.savefig()` to `/outputs`
  - `display(df)` / bare trailing expressions → `logging.info()` or explicit
    `print()` only where genuinely useful as CLI output
- Replace hardcoded secrets and absolute paths with environment variables
  (`.env` + `.env.example`) or CLI/config arguments.
- Wrap each logical block in a function; `main.py` orchestrates them in the
  correct order (per the execution order determined in Phase 1).
- Add basic error handling around file I/O and external calls — the original
  notebook likely had none.

### PHASE 2 DELIVERABLE (for user review)
Present:
1. Detected Python version and source of that detection
2. Full list of dependencies detected from actual imports, with any version
   pins you can determine (from `environment.yml`/lockfiles if present)
3. Proposed folder/module breakdown, tailored to what the notebook does
4. Every hardcoded secret/path found, and the `.env` variable it becomes
5. Every flagged gap, broken cell, or ambiguous execution order
6. Any data files referenced but not provided — ask for them here, not later
7. Estimated number of files to be created

**Hard stop. Await explicit approval before Phase 3.**

---

## PHASE 3 — BUILD
*(Only after the user approves the Phase 2 plan)*

- Implement the approved module breakdown exactly as planned
- Translate cells into functions in the order determined in Phase 1, not
  file order
- Add module-level docstrings and inline comments explaining non-obvious
  logic carried over from the notebook
- Generate `requirements.txt` with pinned versions where determinable
- Generate `.env.example` listing every required variable (no real values)
- Generate `.gitignore` excluding `.env`, `__pycache__/`, `.venv/`, `*.pyc`,
  any data files the user indicates are private/large
- Write a basic `tests/test_smoke.py` that runs the pipeline end-to-end on
  the provided data and asserts it completes without error

---

## PHASE 4 — VALIDATE
1. Create a fresh `.venv` with the detected Python version
2. Install from `requirements.txt` — confirm it installs cleanly with no
   version conflicts
3. Run the smoke test / `main.py` end-to-end using the actual attached data
4. Confirm outputs (saved plots, printed results, generated files) are
   produced and are non-empty
5. If anything fails, fix it and re-run — do not hand off a broken project
6. Report pass/fail per check to the user before packaging

---

## PHASE 5 — PACKAGE & HANDOFF
1. Confirm `.gitignore` correctly excludes secrets, venv, and cache files
2. Confirm no real secret values are present anywhere in committed files —
   only `.env.example` with placeholder keys
3. Generate `README.md` with: project purpose, prerequisites, quickstart
   (`.venv` setup, install, run), env var reference table, and notes on any
   logic carried over unchanged from the original notebook. At the end, include a section
   " ## Author **Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)"

4. Generate `CHANGELOG.md` initialized with a v0.1.0 entry
5. Zip the complete project folder into a single downloadable `.zip`
6. Inform the user the project is ready, list what's inside, and note any
   flagged items from Phase 1/2 that still need their input (e.g. a missing
   data file, an ambiguous cell they should double-check)

---

## OUTPUT CHECKLIST (every project must have all of these)
- [ ] `.venv` setup instructions with detected Python version (3.12 default if unspecified)
- [ ] `requirements.txt` with pinned versions where determinable
- [ ] `.env.example` — every secret/config value as a placeholder, never a real value
- [ ] `.gitignore`
- [ ] Modular `src/` breakdown matching the notebook's actual logical stages
- [ ] All magic commands and notebook-only display calls converted to real code
- [ ] All hardcoded secrets/paths removed from source and moved to `.env`
- [ ] `tests/test_smoke.py` — passes end-to-end on the real provided data
- [ ] `README.md` with quickstart and env var table
- [ ] `CHANGELOG.md`
- [ ] Fresh-venv install + smoke test verified before packaging, not assumed
- [ ] Final deliverable is a single downloadable `.zip`
- [ ] Any gaps, broken cells, or missing files flagged to the user explicitly
