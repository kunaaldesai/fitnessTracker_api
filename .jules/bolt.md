## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.

## 2024-05-23 - Batch Fetching Firestore Documents to Avoid N+1 Queries
**Learning:** Iterating over a list of items and fetching associated Firestore documents individually (e.g., getting exercise names for each workout item) causes a significant N+1 query bottleneck.
**Action:** Always collect all required document IDs in a pre-pass loop, fetch them in a single batch using `db.get_all(refs)` with a fallback to individual gets if needed, and build a lookup map before entering the main processing loop.
