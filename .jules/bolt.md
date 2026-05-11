## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.
## 2024-05-24 - Firestore N+1 Batch Document Retrieval
**Learning:** Batch operations requiring document lookups can cause N+1 query bottlenecks when retrieving documents individually inside loops. The `db.get_all(refs)` method provides a much more efficient way to fetch multiple document references in a single network call.
**Action:** Identify iteration loops calling `.get()` on multiple known Firestore references and replace them with a pre-pass to collect references, a single `db.get_all()` to build a lookup map, and map lookups during the main loop.
