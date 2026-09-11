# AI Teacher Intelligence

A professional teacher workspace for roster management, fast assessment entry, attendance, camera-based AI-assisted exam checking, student performance intelligence, and evidence-linked recommendations.

## Product principle

> Teacher enters evidence once. The system turns it into grades, insights, memory and action.

The academic workspace starts **empty**. The application does not invent students, classes, subjects, assessments, scores, attendance records, or demo exams. A teacher creates the structure they actually use.

## Production-focused release

This release is designed around five priorities:

1. **Fast teacher workflow** — fewer clicks, large touch targets, keyboard-friendly desktop entry.
2. **Identity-aware exam scanning** — papers can be captured in any order; the AI reads the student's visible name/code and the server matches it to the selected exam class.
3. **Safe automation** — high-confidence, complete AI results can be stored automatically in the linked assessment; ambiguous or low-confidence cases remain teacher-review items.
4. **Large batch processing** — up to 150 image files can be queued in one batch on a single application instance, with persistent job progress in the database.
5. **International-ready foundations** — responsive UI, accessibility considerations, audit logging, configurable grading policies, secure file handling, and PostgreSQL-ready persistence.

## Main features

### Roster

- Create classes and students from an empty workspace.
- Student number is assigned automatically from **alphabetical order within the class**, starting at 1.
- Numbers are renumbered when the active roster changes.
- Search, edit, archive, profile, and CSV export.
- No manual student-code field is required in normal UI.

### Assessments

- Editable assessment types.
- Maximum score and weight configuration.
- Explicit Empty / Entered / Zero / Absent / Excused / N/A handling.
- Automatic percentage, weighted average, grade support, and ranking.

### Attendance

- Date-specific records.
- Primary **P / A** touch targets per student.
- Immediate save on tap.
- Previous / next date navigation.
- Secondary Late / Excused options.
- Unique `(student, date)` persistence prevents duplicate attendance rows.

### AI Exam Checker

- Live browser camera and image upload.
- Single-paper quick scan.
- Multi-paper batch scan up to 150 images.
- Student identity extraction from the page.
- Name-first matching against the exam class roster; sequential class number is corroborating evidence only because it can change when students are added, removed, or renamed.
- Question-level structured grading with score, confidence, reason, mistake type, topic, and feedback.
- Teacher review, edit, accept, reject, and audit trail.
- Safe automatic storage when identity, question coverage, confidence, and score integrity gates all pass.
- Existing final scores are never silently overwritten.

### Student intelligence

- Assessment history.
- Pass/fail against school-configured pass mark.
- Attendance summary.
- Repeated mistake memory.
- Recommendations based on stored evidence.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy + Alembic
- SQLite for local development
- PostgreSQL-ready schema
- Vanilla JavaScript/CSS responsive frontend
- PWA application shell
- Pillow image preprocessing
- Google `google-genai` SDK for Gemini
- PyJWT + password hashing

## Local startup

Python 3.12 is recommended.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open:

`http://127.0.0.1:8000/`

API documentation:

`http://127.0.0.1:8000/docs`

### Local access

Development mode provides a local demo teacher account for smoke testing:

```text
Email: teacher@example.com
Password: Teacher123!
```

The public-facing UI also supports **Create account**. Each newly registered teacher receives a new isolated workspace and starts with no students, classes, assessments or attendance data. Disable the demo account for production. Change local demo credentials and `SECRET_KEY` before deployment.

## Gemini configuration

Put the API key only in `.env`:

```env
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-3.8-flash
```

The server validates structured output before it can affect stored results. Without a Gemini key, the roster, assessment, attendance, analytics, and manual grading workflows still function.

## Camera and batch rules

The browser camera uses `getUserMedia()` when the browser permits it. Deployed camera usage should use HTTPS. Local `127.0.0.1` development is supported.

Batch scanning is capped at 150 image files per job in the application UI. This is an application-level cap, not a claim about Gemini's service limits.

## Tests

```bat
python -m pytest -q
python scripts/benchmark_batch_mock.py
node --check app/static/app.js
```

The release includes unit/API tests for calculation rules, missing/zero semantics, ranking, attendance, identity matching, auto-storage gating, duplicate protection, and schema validation, plus a synthetic 120-paper mock benchmark that excludes external Gemini network/model latency.

## Production deployment notes

For a real school deployment:

- Use PostgreSQL instead of local SQLite.
- Put uploaded papers in private object storage.
- Use HTTPS/TLS.
- Store secrets in environment/managed secret storage.
- Add rate limiting and centralized logs.
- Back up the database and define retention/deletion rules.
- For multi-instance/horizontally scaled processing, move batch workers from the in-process thread pool to a durable queue/worker service such as Redis + Celery/RQ or a managed job system.
- Benchmark the exact Gemini model, account tier, image sizes, and school paper formats before committing to an SLA.

## Documentation

- `docs/RESEARCH.md`
- `docs/ARCHITECTURE.md`
- `docs/DATABASE.md`
- `docs/AI_GRADING.md`
- `docs/SECURITY.md`
- `docs/TESTING.md`
- `docs/DEPLOYMENT.md`
- `docs/GEMINI_SETUP.md`
- `docs/USER_GUIDE.md`
- `docs/ROADMAP.md`
- `docs/RELEASE_NOTES.md`


## Browser/PWA
Run locally at `http://127.0.0.1:8000`. On a supported Chromium browser, the app can be installed as a standalone PWA when served from HTTPS (or localhost/127.0.0.1 during development).

## Production environment
Set `APP_ENV=production`, `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, `ALLOWED_ORIGINS`, `PUBLIC_APP_URL`, `DATABASE_URL` and `GEMINI_API_KEY`.

## Attendance behavior
The class register remembers the latest date with saved attendance. Re-entering a class reopens that saved date instead of silently resetting to today. Use **New day** when you intentionally want to start another date. **History** lists saved dates.

## Reports
Reports now support per-student overview, attendance, score, middle-term, final and full transcript output, with print and CSV export.


## Final release notes

### Offline-first daily work
Attendance and score writes can be queued locally when offline and synchronized later. Previously cached roster/class/attendance/assessment data can be read locally. Gemini AI is intentionally online-only. See `docs/OFFLINE_FIRST.md`.

### Grading choice
Each assessment can be configured as `Teacher enters scores` or `AI checks papers`. Manual assessments stay in the regular score grid; AI assessments enable the camera checker.

### Android
`mobile/` contains the Capacitor 8 Android wrapper source. Run `mobile/npm install`, `npx cap add android`, `npx cap sync android`, and open the project in Android Studio. See `docs/ANDROID_RELEASE.md`.
