# Production readiness

## Verified in this source package
- automated backend suite passes
- Python compilation passes
- JavaScript syntax check passes
- fresh Alembic migration through revision 0007 passes
- offline sync API is idempotent
- manual and AI grading modes are separated at the assessment level
- security headers and cookie-based authentication are implemented
- no real API secrets are packaged

## Production safeguards
- teacher remains final authority for uncertain/high-stakes AI results
- AI output is schema validated
- identity confidence and question confidence gate automatic storage
- missing score is not treated as zero
- audit history records material changes
- workspace access is scoped to the authenticated school

## Required before a public school launch
- real-paper handwritten benchmark across the target subjects/languages
- latency/quota testing against the selected Gemini model and account tier
- Android real-device camera/permission regression testing
- encrypted-at-rest local mobile storage using platform-backed keys for sensitive student data
- managed object storage for answer-sheet images rather than ephemeral local server disk
- centralized rate limiting and monitoring across multiple API instances
- backup/restore drill and retention/deletion verification
- penetration test and dependency vulnerability scan
- signed release APK/AAB and crash reporting

The package is production-oriented source, not a claim that these external operational controls have already been completed.
