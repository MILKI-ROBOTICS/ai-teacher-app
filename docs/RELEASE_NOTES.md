# Release notes

## v6 final production-oriented release
- Added local IndexedDB cache and durable offline outbox for attendance and score mutations.
- Added idempotent `/api/sync` server reconciliation.
- Added assessment-level manual vs AI grading mode.
- Updated Gemini integration to the current Interactions API with structured output.
- Added Capacitor 8 Android wrapper source.
- Added production readiness/offline/Android release documentation.
- Kept AI high-stakes decisions teacher-controlled.

# Release 5.1 — Production access and browser UX

- Added self-service Sign up, Sign in, and Sign out flows.
- Each new account gets an isolated workspace/school boundary.
- Added password confirmation and stronger password rules.
- Added HttpOnly session cookies, CSRF protection, session-version invalidation, login throttling, and production secret validation.
- Removed the custom in-app PWA install button and `beforeinstallprompt` dependency; browser-native installation remains available.
- Added a more descriptive AI Teacher app icon, favicon, Apple touch icon, and richer manifest shortcuts.
- Added professional authentication layout and responsive mobile navigation polish.
- Added Render deployment blueprint with managed Postgres.
- Hardened cross-workspace authorization on core teacher data endpoints.
- Kept AI grading teacher-controlled and schema-validated.
