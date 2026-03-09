## 2024-05-23 - Firestore N+1 Optimization
**Learning:** Firestore subcollection queries (e.g. fetching sets for each workout item) cause N+1 bottlenecks. Since Firestore SDK is thread-safe and these are I/O bound, `concurrent.futures.ThreadPoolExecutor` is an effective pattern to parallelize these queries without changing the data model.
**Action:** Identify loops performing DB queries and refactor to use `executor.map` for parallel execution.

## 2024-05-24 - Firestore Reference get_all Optimization
**Learning:** When retrieving known documents by their IDs or references, making sequential `ref.get()` calls in a loop causes an N+1 query problem that slows down backend operations significantly, especially when creating workouts with many exercises. `db.get_all(refs)` provides a native way to fetch multiple documents in a single batch request, which is much more efficient than spinning up threads for individual calls.
**Action:** Replace `for ref in refs: doc = ref.get()` patterns with batch retrievals using `db.get_all(refs)`. Ensure fallbacks are present for robustness.
