# AI Teacher Intelligence — Android build

This directory wraps the same lightweight PWA frontend with Capacitor 8. Core offline teacher workflows use IndexedDB in the WebView; online synchronization goes to the FastAPI backend. AI grading is intentionally online-only because Gemini is a network service.

## Prerequisites
- Node.js 22 LTS or later compatible with your Capacitor toolchain
- Android Studio
- Android SDK + platform tools
- JDK 21

## Configure backend URL
Edit `web/index.html` and replace `__ATI_API_BASE__` with the production HTTPS API origin. Example:
`https://ai-teacher-app-u0hk.onrender.com`

## Build
```powershell
npm install
npx cap add android
npx cap sync android
npx cap open android
```
Then in Android Studio choose a connected device/emulator and Build > Build APK(s).

Or after the Android platform has been added:
```powershell
npm run build:android
```

## Offline behavior
- attendance, previously loaded roster/class data, and score writes can be kept locally
- writes are queued and retried when connection returns
- server uses idempotent operation IDs to prevent duplicate sync
- Gemini AI requires internet

Do not ship with a demo API URL or development secret. Use an HTTPS production API and a production `SECRET_KEY`.
