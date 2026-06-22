# Logmaxxing Firebase API

Firebase Functions backend for the Logmaxxing workout tracker.

## Structure

```text
.
├── firebase.json
├── firestore.indexes.json
├── public/
│   └── index.html
├── functions/
│   ├── main.py
│   ├── requirements.txt
│   ├── config/
│   │   └── db.py
│   ├── handlers/
│   │   └── fitness_handlers.py
│   ├── helpers/
│   │   ├── auth_helpers.py
│   │   ├── fitness_helpers.py
│   │   └── fitness_profile_helpers.py
│   └── routes/
│       └── fitness.py
└── tests/
    ├── test_fitness_api.py
    └── utils.py
```

## API

All deployed endpoints are under:

```text
/api/fitness/
```

Every request requires:

```text
Authorization: Bearer <Firebase ID token>
```

The API derives the user from the verified Firebase token. Clients should not send user ids or owner ids.

Main endpoints:

```text
GET  /api/fitness/day/?date=YYYY-MM-DD
GET  /api/fitness/exercise-options/
GET  /api/fitness/analytics/
GET  /api/fitness/records/
GET  /api/fitness/profile/
POST /api/fitness/profile/
GET  /api/fitness/profile/weight-history/
POST /api/fitness/profile/weight-history/create/
POST /api/fitness/profile/weight-history/<entry_id>/update/
POST /api/fitness/profile/weight-history/<entry_id>/delete/
POST /api/fitness/exercises/create/
POST /api/fitness/exercises/<exercise_id>/update/
POST /api/fitness/exercises/<exercise_id>/delete/
POST /api/fitness/exercises/reorder/
GET  /api/fitness/exercises/last-sessions/
GET  /api/fitness/exercises/previous-workout/
POST /api/fitness/exercises/copy-from-date/
GET  /api/fitness/exercise-history/
GET  /api/fitness/workout-calendar/
```

## Data Model

- `users/{uid}` stores the authenticated user's profile and `fitness_profile`.
- `users/{uid}/weight_entries/{YYYY-MM-DD}` stores one body-weight entry per calendar date.
- `users/{uid}/workout_days/{YYYY-MM-DD}` stores day-level workout summaries and rollups.
- `users/{uid}/workout_days/{YYYY-MM-DD}/exercise_entries/{entry_id}` stores logged exercise entries.
- `users/{uid}/exercise_definitions/{exercise_key}` stores user-specific exercise options derived from logged custom exercises.
- `users/{uid}/exercise_records/{exercise_key}` stores per-exercise personal-record rollups.
- `exercise_catalog/{exercise_key}` stores the seeded default exercise library.

The old top-level `fitness_exercises` collection is no longer written by the API. Leave any existing documents untouched unless an explicit cleanup or migration is approved.

Client Firestore access is denied by default in `firestore.rules`; the mobile app talks to Cloud Functions over HTTPS and the Admin SDK bypasses client rules.

## Warehouse

Firestore is the app-serving store. Cross-user product analytics should use a BigQuery export, not mobile app reads or broad Firestore scans.

Recommended Firebase extension: `firebase/firestore-bigquery-export`.

Recommended BigQuery dataset: `logmaxxing_raw` in US multi-region, matching the current Firestore database location family (`nam5`).

Recommended exported collection paths:

```text
users/{uid}/workout_days
users/{uid}/workout_days/{dayId}/exercise_entries
users/{uid}/weight_entries
users/{uid}/exercise_definitions
analytics_events
```

Configured extension instances:

```text
bq-workout-days           -> users/{uid}/workout_days
bq-exercise-entries       -> users/{uid}/workout_days/{dayId}/exercise_entries
bq-weight-entries         -> users/{uid}/weight_entries
bq-exercise-definitions   -> users/{uid}/exercise_definitions
bq-analytics-events       -> analytics_events
```

The extension parameter files live in `extensions/*.env`. They are deploy config, not application secrets.

## Local Tests

```bash
python3 -m unittest discover -s tests
```

Tests use mocked Firebase Auth and in-memory Firestore. Do not hit live databases from unit tests.

## Deploy

The clean `/api/fitness/**` path is provided by Firebase Hosting rewrites, so deploy Functions and Hosting together after route or rewrite changes:

```bash
firebase deploy --only functions,hosting,firestore:rules,firestore:indexes --project fitness-tracker-39bca
```

Deploy the BigQuery export extension manifest with:

```bash
firebase deploy --only extensions --project fitness-tracker-39bca
```

Use `--force` when replacing or deleting old function exports in a non-interactive deploy:

```bash
firebase deploy --only functions,hosting,firestore:rules,firestore:indexes --project fitness-tracker-39bca --force
```
