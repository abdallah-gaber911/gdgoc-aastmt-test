# GDGoC AASTMT — Python From Zero Assessment Platform
## Project Handoff Documentation (`HANDOFF.md`)

**Created by:** AI Team | Google Developer Groups on Campus (GDGoC) AASTMT  
**Platform:** Python From Zero Assessment & Interactive Quiz Platform  
**Target Environment:** Local Python 3.10+ / Managed Web Preview  
**Default Port:** `3000` (`http://127.0.0.1:3000`)

---

## 1. Executive Summary

This platform is an assessment and gamified practice environment designed for GDGoC AASTMT's **"Python From Zero"** course. It provides students with three 20-question quizzes covering core Python fundamentals, in-browser code execution using Pyodide (WebAssembly), instant feedback, and a real-time global leaderboard.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Client Browser                        │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │    SPA (Vanilla JS)   │       │  Pyodide Web Worker   │  │
│  │  app.js / editor.js   │<─────>│  (Isolated Execution) │  │
│  └───────────┬───────────┘       └───────────────────────┘  │
└──────────────┼──────────────────────────────────────────────┘
               │ HTTP REST API
               ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend Server (Vercel)                │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   main.py (Routes)    │──────>│  question_bank.py     │  │
│  └───────────┬───────────┘       │  (Grading & Questions)│  │
│              │                   └───────────────────────┘  │
│              ▼                                              │
│  ┌───────────────────────┐                                  │
│  │   storage.py          │                                  │
│  │   (SQLAlchemy)        │                                  │
│  └───────────┬───────────┘                                  │
└──────────────┼──────────────────────────────────────────────┘
               ▼
   [ Supabase PostgreSQL ] (via Transaction Connection Pooler & NullPool)
```

### Key Architectural Decisions:
1. **Zero-Execution Server Risk**: Student code is **never** executed on the backend server. Code runs completely sandboxed in the learner's browser via a dedicated Web Worker loading Pyodide (Python on WebAssembly).
2. **Serverless-Ready Database Storage**: Data persists in Supabase PostgreSQL via connection pooling (Transaction mode, port 6543, SSL enabled). The storage layer uses SQLAlchemy with `NullPool` (safe for serverless cold starts) and falls back to local SQLite when `DATABASE_URL` is not set. First-score enforcement is guaranteed at the database level (`ON CONFLICT DO NOTHING`).
3. **First-Score Policy**: To prevent score farming, only the student's first completed quiz submission counts toward the leaderboard.

---

## 3. Directory & File Structure

```text
GDGoc-AASTMT-Game_Test_FInale/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI entry point, endpoints, static file mounting
│   ├── storage.py            # Thread-safe and process-safe JSON storage engine
│   ├── question_bank.py      # Bank loader, question sanitizer, grading logic
│   ├── data/
│   │   └── questions.json    # Complete bank of 60 questions & test suites
│   └── static/
│       ├── index.html        # Single-page application HTML
│       ├── styles.css        # GDGoC Google Material styled UI
│       ├── app.js            # Routing, session, quiz navigation, leaderboard
│       ├── editor.js         # CodeMirror editor, answer components, testing runner
│       └── runner.worker.js  # Dedicated Pyodide WebAssembly runner
├── public/
│   └── manus-routes.json     # Route manifest
├── tests/
│   ├── __init__.py
│   └── test_app.py           # Pytest suite covering API, bank, grading, concurrency
├── .gitignore                # Git ignore rules
├── Makefile                  # CLI task automation commands
├── plan.md                   # Initial implementation blueprint
├── README.md                 # Public overview and quick-start
├── requirements.txt          # Python dependencies
├── TODO.md                   # Requirements and completion checklist
└── HANDOFF.md                # This comprehensive handoff document
```

---

## 4. Environment Setup & Execution

### Prerequisites
- Python 3.10 or higher
- Pip

### Quick Start

1. **Activate virtual environment (optional but recommended):**
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the server:**
   ```bash
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
   ```

4. **Access the application:**
   - **Frontend App:** [http://127.0.0.1:3000](http://127.0.0.1:3000)
   - **Interactive API Docs (Swagger):** [http://127.0.0.1:3000/docs](http://127.0.0.1:3000/docs)
   - **Health Check Endpoint:** [http://127.0.0.1:3000/api/health](http://127.0.0.1:3000/api/health)

---

## 5. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status |
| `POST` | `/api/session` | Create or resume a student session (`{student_id, name}`) |
| `GET` | `/api/session` | Fetch active session by `student_id` |
| `GET` | `/api/questions/{quiz_id}` | Fetch 20 sanitized questions for Quiz 1, 2, or 3 (omits answers) |
| `GET` | `/api/progress/{quiz_id}` | Retrieve in-progress draft answers |
| `PUT` | `/api/progress/{quiz_id}` | Auto-save answers while taking a quiz |
| `POST` | `/api/check` | Instant evaluation for a question without submitting quiz |
| `POST` | `/api/submit/{quiz_id}` | Finalize quiz attempt and update leaderboard score |
| `GET` | `/api/leaderboard` | Get ranked leaderboard entries |
| `GET` | `/manus-routes.json` | Page route manifest |

---

## 6. Question Bank & Curriculum Mapping

The question bank in `app/data/questions.json` has 60 unique questions across three quizzes:

- **Quiz 1 (Topics 1–6):**
  - Topics: Print/Output, Comments, Variables, Data Types, Operators, Strings.
  - Mix: 7 Easy (1 pt), 8 Medium (2 pts), 5 Hard (3 pts).
- **Quiz 2 (Topics 7–13):**
  - Topics: Input/Type Conversion, Conditions, Lists, Tuples, Sets, Dictionaries.
  - Mix: 6 Easy (1 pt), 8 Medium (2 pts), 6 Hard (3 pts).
- **Quiz 3 (Topics 14–15 & Mixed Challenges):**
  - Topics: Loops (`for`/`while`), Range, Break/Continue, Functions, Print vs Return, Defaults, Algorithms (FizzBuzz, Prime check, Shopping cart).
  - Mix: 5 Easy (1 pt), 8 Medium (2 pts), 7 Hard (3 pts).

### Supported Question Types:
- `choice`: Multiple Choice Questions
- `fill`: Fill-in-the-blank (exact match or list of accepted variations)
- `output`: Output prediction
- `fix`: Bug-fixing in code snippets
- `code`: Live Python coding against multiple test cases

---

## 7. Storage Engine Details

- **Backend**: Supabase PostgreSQL (Production / Serverless via `DATABASE_URL`) with local SQLite fallback for development and testing.
- **Connection Architecture**:
  - Uses Supabase Transaction Connection Pooler (port 6543, `sslmode=require`).
  - SQLAlchemy configured with `NullPool` to avoid connection exhaustion across serverless function instances.
  - Safe automatic table creation (`CREATE TABLE IF NOT EXISTS`) for `sessions`, `progress`, and `submissions`.
- **First-Score Policy**:
  - Enforced at the database constraint level: `INSERT ... ON CONFLICT (student_id, quiz_id) DO NOTHING`.
  - Repeat submissions never overwrite the initial attempt, even under concurrent requests.
- **Leaderboard Ranking Logic**:
  1. Primary: `total_points` (descending)
  2. Secondary: `total_solved` (descending)
  3. Tertiary: `name` (alphabetical ascending for stable order)

---

## 8. Automated Testing

Run the test suite at any time with:
```bash
python -m pytest -v
```

The test suite validates:
- Question bank integrity (exactly 60 questions, valid schema, no duplicates, accurate difficulty distribution)
- Public question payload sanitization (no leak of answers or explanations)
- Session lifecycle & auto-saving of progress
- Multiple-choice and hidden code test evaluation
- First-score anti-farming enforcement (repeat submissions cannot overwrite the original score)
- Multi-threaded concurrent writes to `leaderboard.json` without corruption

---

## 9. Next Steps & Recommendations for Maintainers

1. **Round 2 Module:**
   - Round 2 is currently marked as "Locked / Coming Soon" in `app/static/app.js`.
   - To unlock, implement Quiz 4-6 definitions and update the unlocked condition in `app.js`.
2. **Production Deployment on Vercel:**
   - Deployed as a serverless Python FastAPI application on Vercel (`api/index.py`, `vercel.json` with `@vercel/python`).
   - Uses Supabase PostgreSQL connection pooler configured via the `DATABASE_URL` environment variable.
3. **Authentication:**
   - The current setup uses lightweight name + client UUID sessions. For formal competitions, consider adding OAuth / Google Sign-In via Firebase or Google Identity Services.

---
*Maintained with care by AI Team · GDG on Campus AASTMT.*
