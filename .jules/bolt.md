## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.
## 2025-02-12 - Sequential Firestore deletes
**Learning:** Sequentially deleting nested Firestore items (like sets, items, and the parent workout) causes unnecessary network overhead and acts as a bottleneck.
**Action:** Group multiple delete operations using `db.batch()` and remember to commit and reset the batch every 490 operations to avoid Firestore limit errors.
