# Android release

The Android client is a Capacitor 8 wrapper around the same lightweight web application. Capacitor is a web-native runtime intended for Android/iOS/PWA applications and supports camera, filesystem and network plugins.

## Why this stack
- same business/UI code works in browser and Android
- small front-end surface with no heavy runtime framework
- IndexedDB provides persistent local cache/outbox in the WebView
- FastAPI remains the central authoritative API
- Gemini remains server-side and is never shipped inside the APK

## Build prerequisites
- Node.js 22 LTS or current Capacitor-compatible Node
- JDK 21
- Android Studio
- Android SDK + build tools

## Build steps
```powershell
cd mobile
npm install
# set __ATI_API_BASE__ in web/index.html to the production HTTPS API origin
npx cap add android
npx cap sync android
npx cap open android
```
Then build a signed APK/AAB from Android Studio.

A helper is included at `scripts/build_android.ps1`.

## Release security
- never ship a development API URL or development SECRET_KEY
- use HTTPS for the production API
- keep Gemini credentials on the server
- configure backup, monitoring, rate limiting and object storage for uploaded answer sheets
- run a security review and real-device test pass before public distribution

This environment did not contain a working Android SDK/Gradle toolchain, so the binary APK itself is not produced here; the project contains the complete Capacitor build source and scripts.

Reference: https://capacitorjs.com/docs
