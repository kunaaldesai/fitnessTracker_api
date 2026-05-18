## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.
## 2024-05-23 - Batch Firestore Document Fetching
**Learning:** Performing multiple individual `document().get()` calls in a loop causes an N+1 query performance bottleneck. Instead, collect all document references in a pre-pass loop and use `db.get_all(references)` to fetch them all in a single batch read.
**Action:** When needing to fetch multiple documents in a loop, always use a pre-pass to collect references and batch fetch them using `db.get_all()`. Create a map of the results to use in the original loop.
