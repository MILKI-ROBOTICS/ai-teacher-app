# Deployment

## Local

`python -m uvicorn app.main:app --reload` serves the product at `http://127.0.0.1:8000`.

## Browser link / production URL

The application is web-native and PWA-ready. A public browser link requires deployment behind HTTPS and a DNS hostname, for example `https://teacher.example.org`. Set `PUBLIC_APP_URL` and `ALLOWED_ORIGINS` to the deployed origin. For production, prefer a `__Host-` cookie name, `SESSION_COOKIE_SECURE=true`, and no wildcard CORS origins. Chromium-based browsers require a manifest and HTTPS (localhost/127.0.0.1 is allowed for development) before offering PWA installation.

## Production essentials

- HTTPS/TLS and HSTS
- `APP_ENV=production`
- cryptographically random `SECRET_KEY`
- `SESSION_COOKIE_SECURE=true`
- PostgreSQL instead of SQLite for multi-user production
- private object storage for answer sheets
- regular encrypted backups
- monitored worker/service process
- centralized logs and rate limiting across instances
