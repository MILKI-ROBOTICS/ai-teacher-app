# Production research notes

## Product direction
The product is positioned as a teacher productivity and assessment-intelligence platform, not a generic school-management or gradebook clone. The differentiating loop is: roster/evidence capture → AI-assisted interpretation → teacher verification → durable academic record → longitudinal insight.

## PWA and browser delivery
Modern Chromium-based browsers use the web app manifest and browser-native installation UI. Installability requires a manifest with the app name, 192px and 512px icons, start URL, and a display mode; production installation requires HTTPS, while localhost/127.0.0.1 are valid for development. The application therefore keeps install behavior in the browser rather than forcing a custom in-app installer. `beforeinstallprompt` remains a non-standard, Chromium-only mechanism, so it is intentionally not required by the core UX.

Sources:
- MDN, “Making PWAs installable”: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
- MDN, “Trigger installation from your PWA”: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/How_to/Trigger_install_prompt

## Gemini vision and structured output
Gemini models support native multimodal image understanding and structured JSON/schema-constrained outputs. The grading service therefore sends the answer-sheet image with the exam context and validates the returned Pydantic structure before any result can enter the review/storage workflow.

Sources:
- Google AI for Developers, “Image understanding”: https://ai.google.dev/gemini-api/docs/image-understanding
- Google AI for Developers, “Structured outputs”: https://ai.google.dev/gemini-api/docs/structured-output
- Google AI for Developers, “Getting started”: https://ai.google.dev/gemini-api/docs/get-started

## Authentication and CSRF
The application uses an HttpOnly session cookie, a readable CSRF cookie paired with a custom request header for state-changing browser requests, explicit logout invalidation via a server-side session version, throttled failed login attempts, and production secret validation. The browser front end does not keep authentication tokens in localStorage.

Sources:
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP CSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Render delivery
Render supports FastAPI services with a `uvicorn` start command, environment variables/secrets, managed PostgreSQL, and optional persistent disks. The included `render.yaml` is a repeatable deployment blueprint. Student answer-sheet uploads should use a persistent disk or an object-storage adapter in production because a normal web-service filesystem is ephemeral.

Sources:
- Render, FastAPI deployment: https://render.com/docs/deploy-fastapi
- Render, Environment variables: https://render.com/docs/configure-environment-variables
- Render, Persistent disks: https://render.com/docs/disks
- Render, PostgreSQL: https://render.com/docs/postgresql
