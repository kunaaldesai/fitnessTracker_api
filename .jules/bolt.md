## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.

## 2024-05-23 - Firestore N+1 Optimization 2
**Learning:** Firestore N+1 query bottlenecks can occur when iterating over an array to fetch related documents (e.g. missing names for exercises).
**Action:** Use a pre-pass loop to collect missing document IDs, fetch them in a single batch using `db.get_all(refs)`, build a dictionary lookup map, and then replace the individual database queries with map lookups in the main iteration loop.
