## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.

## 2024-06-15 - Firestore Batch Writes Optimization
**Learning:** Sequential Firestore deletions using `reference.delete()` within nested collections (e.g., deleting workout items and sets recursively) cause N+1 database roundtrips and heavily degrade backend performance. Firestore allows grouping these mutations using `db.batch()`, drastically reducing network overhead.
**Action:** For loops performing sequential writes/deletes, track operation counts to safely chunk batches under Firestore's 500 operation limit (e.g., 490), call `batch.commit()`, and reset the batch safely.
