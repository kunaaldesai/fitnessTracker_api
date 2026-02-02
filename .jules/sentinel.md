## 2025-02-18 - Exception Leakage in API Responses
**Vulnerability:** API endpoints were returning raw exception strings (`str(e)`) in the `details` field of 500 responses.
**Learning:** Generic `except Exception as e` blocks that return `e` to the user are a common source of information leakage (paths, database errors, internal logic).
**Prevention:** Always log the full exception on the server and return a sanitized, generic error message to the client.

## 2026-02-02 - Privilege Escalation via Mass Assignment
**Vulnerability:** Users could become admins by injecting `isAdmin: true` in `createUser` or `updateUser` payloads because the `data` dictionary was passed directly to Firestore.
**Learning:** Blindly passing `request.get_json()` to database methods allows users to modify fields they shouldn't access (Mass Assignment).
**Prevention:** Always whitelist allowed fields or explicitly strip sensitive fields (like `isAdmin`, `isVerified`) before saving to the database.
