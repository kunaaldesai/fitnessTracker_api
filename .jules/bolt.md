## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.
## 2026-06-01 - Batching nested Firestore deletions
**Learning:** Sequential Firestore document deletions (e.g., iterating through workout items and their sets to delete each one individually) creates a significant N+1 network bottleneck. Using `db.batch()` to group deletes and commit them in chunks (safely capped at 490 to stay under the 500 operation limit) resolves the bottleneck while remaining synchronous and avoiding thread exhaustion from thread pools.
**Action:** When performing multiple related writes/deletes (like cascading deletes of nested collections), always refactor to use Firestore batched operations instead of looping individual `delete()` calls or parallelizing them across threads.
