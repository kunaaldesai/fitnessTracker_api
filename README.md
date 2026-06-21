# FitTrack Firebase API

Firebase Functions backend for the FitTrack workout tracker.

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
- `fitness_exercises/{exercise_id}` stores logged exercises using `owner_uuid = uid`.

The old nested workout/user endpoint schema is no longer used.

## Local Tests

```bash
python3 -m unittest discover -s tests
```

Tests use mocked Firebase Auth and in-memory Firestore. Do not hit live databases from unit tests.

## Deploy

The clean `/api/fitness/**` path is provided by Firebase Hosting rewrites, so deploy Functions and Hosting together after route or rewrite changes:

```bash
firebase deploy --only functions,hosting --project fitness-tracker-39bca
```

Use `--force` when replacing or deleting old function exports in a non-interactive deploy:

```bash
firebase deploy --only functions,hosting --project fitness-tracker-39bca --force
```
