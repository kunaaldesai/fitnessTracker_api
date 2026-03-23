# edit here

## Project structure
```
.
├── .jules/
│   └── sentinel.md
├── JULES.md
├── README.md
├── firebase.json
├── firestore.indexes.json
├── functions/
│   ├── main.py
│   ├── requirements.txt
│   ├── config/
│   │   └── db.py
│   ├── handlers/
│   │   ├── users_handlers.py
│   │   └── workouts_handlers.py
│   ├── helpers/
│   │   └── workouts_helpers.py
│   └── routes/
│       ├── error_codes.py
│       ├── users.py
│       └── workouts.py
└── tests/
    ├── test_security.py
    ├── test_security_exploit.py
    ├── test_users_routes.py
    ├── test_workouts_routes.py
    └── utils.py
```

## Running Tests
Run tests from repo root with `python -m unittest discover -s tests` after installing dependencies via `pip install -r functions/requirements.txt`.

# keep this section
firebase emulators:start --project fitness-tracker-39bca
firebase deploy --only functions --project fitness-tracker-39bca
