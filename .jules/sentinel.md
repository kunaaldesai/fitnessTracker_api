## 2025-02-18 - Exception Leakage in API Responses
**Vulnerability:** API endpoints were returning raw exception strings (`str(e)`) in the `details` field of 500 responses.
**Learning:** Generic `except Exception as e` blocks that return `e` to the user are a common source of information leakage (paths, database errors, internal logic).
**Prevention:** Always log the full exception on the server and return a sanitized, generic error message to the client.
