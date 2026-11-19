# Python From Zero — GDGoC AASTMT

A lightweight Round 1 Python assessment platform created by the **AI Team | GDG on Campus AASTMT**. It includes three 20-question quizzes, an in-browser Python runner, progress saving, and a production-grade Supabase Postgres-backed leaderboard deployed on Vercel.

## Run locally

Requirements: Python 3.10+ and an internet connection for the optional CodeMirror/Pyodide browser assets.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
```

Open <http://127.0.0.1:3000>. After the one-time dependency installation, the single command to run the app is `uvicorn app.main:app --reload --host 127.0.0.1 --port 3000`.

## What is included

- Name-only onboarding and a Round 1 dashboard with Quiz 1, Quiz 2, Quiz 3, a locked Round 2 teaser, and a live leaderboard.
- Sixty unique questions based on the supplied Python session syllabus, with easy/medium/hard difficulty and 1/2/3-point values.
- Multiple-choice, fill-in, output-prediction, bug-fixing, and function-writing questions.
- CodeMirror syntax highlighting and Tab indentation. Pyodide executes snippets inside a browser Web Worker, not in the FastAPI process. Run Code displays output/errors; Check Answer grades the response against the question tests. The assessment questions do not depend on blocking `input()`.
- Progress, student names, quiz points, and totals in Supabase PostgreSQL via SQLAlchemy and Supabase Transaction Connection Pooler (port 6543, SSL mode required). Fallback to local SQLite when `DATABASE_URL` is omitted.

## Scoring and attempt policy

A given name-only browser session (session ID) can submit each quiz once. The **first completed score** is kept; repeat submissions from that session cannot replace it. Easy questions award 1 point, Medium 2, and Hard/Tricky 3. The leaderboard ranks by total points across all three quizzes, with total questions solved as the next tie-breaker, then name for a stable display order.

## Storage and deployment

The platform is deployed to Vercel serverless (`@vercel/python` via `api/index.py` and `vercel.json`) and backed by Supabase PostgreSQL. Database operations use SQLAlchemy with `NullPool` (safe for serverless cold starts) connecting through Supabase's transaction pooler. The First-Score Policy is enforced at the database layer via `INSERT ... ON CONFLICT (student_id, quiz_id) DO NOTHING` so repeat submissions can never overwrite original results.

Python code is isolated from the API server in a Web Worker, with a browser-side execution timeout and bounded captured output. Browser-side code results and name-only sessions do not provide cryptographic identity or strong anti-cheat guarantees: a determined user can alter client requests or create another browser session, and students with identical names are not automatically merged. The API applies the requested first-score-per-quiz policy for a given session ID, but this design is not a proctored or tamper-proof assessment system.

## Checks

```bash
python -m pytest -q
```

Health endpoint: `GET /api/health`. Question payloads are available at `GET /api/questions/{1|2|3}`; answer keys are not returned. The only page route is `/`; APIs and assets are not part of the route manifest.

---

**Created by AI Team | GDG on Campus AASTMT**
