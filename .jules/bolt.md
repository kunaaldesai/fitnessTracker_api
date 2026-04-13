## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.

## 2025-05-18 - Batch get vs Individual gets
**Learning:** We had an N+1 queries bug in `start_workout` where we were iterating over exercises and calling `.get()` for each of their IDs to get their names.
**Action:** Always batch Firestore reads by using `db.get_all(refs)` outside the loop to gather necessary document names via a lookup map, and fallback to individual gets if `get_all` is not supported on the specific interface context.
