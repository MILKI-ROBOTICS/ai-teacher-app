# Offline-first architecture

The application treats device-local state as the immediate UI source for the daily workflows that must survive unreliable connectivity. This follows Android's current offline-first guidance: local data is read first, writes are persisted locally, and queued work is synchronized when connectivity returns.

## Offline now supported
- previously cached workspace, classes, roster, attendance and assessment data can be displayed without a network call
- attendance writes are queued locally when the network is unavailable
- score writes are queued locally when the network is unavailable
- queued mutations are retried when connectivity returns
- sync uses idempotent operation IDs so a retry does not create a duplicate record
- online recovery triggers a refresh after synchronization

## Online-only
- Gemini AI grading
- AI identity extraction
- AI feedback generation
- new cloud account creation/login
- reports that require uncached server data

## Important storage boundary
Browser IndexedDB/WebView storage is persistent and origin-scoped, but it is not equivalent to a hardware-backed encrypted database. For a high-sensitivity school deployment, the Android release should add encrypted local storage backed by Android Keystore/SQLCipher and a local device unlock policy. This release therefore does not claim encrypted-at-rest local student data.

## Sync model
The server is authoritative. Each queued mutation carries an operation ID. The `/api/sync` endpoint records applied operation IDs and safely ignores duplicate retries. Android should also trigger synchronization on application resume and network recovery.

References:
- Android Developers, Build an offline-first app: https://developer.android.com/topic/architecture/data-layer/offline-first
- Android Developers, Build for Billions — connectivity: https://developer.android.com/docs/quality-guidelines/build-for-billions/connectivity
