# Security

The application is designed for HTTPS deployment with authenticated, role-aware APIs, secure password hashing, audit logs, private uploads, security response headers and a server-side Gemini key. Production should set `APP_ENV=production`, use a real random `SECRET_KEY`, set `SESSION_COOKIE_SECURE=true`, configure `ALLOWED_ORIGINS` to the deployed origin(s), and terminate TLS at the deployment edge.

Browser sessions use an HttpOnly cookie in addition to a backward-compatible bearer response. Sensitive state-changing operations remain authenticated. Login failures are throttled per client in-process; a multi-instance deployment should replace this with a shared rate limiter.

Student data must not be exposed through public URLs, exports should be access-controlled, and backups require equivalent protection.
