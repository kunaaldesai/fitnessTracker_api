# edit here

## Project structure
```
.
├── README.md
├── api/
├── firebase-debug 2.log
├── firebase.json
├── firestore.indexes.json
└── functions/
    ├── main.py
    ├── requirements.txt
    ├── config/
    │   └── db.py
    ├── handlers/
    │   ├── users_handlers.py
    │   └── workouts_handlers.py
    ├── helpers/
    │   └── workouts_helpers.py
    ├── routes/
    │   ├── error_codes.py
    │   ├── users.py
    │   └── workouts.py
    └── venv/
```

# keep this section
firebase emulators:start --project fitness-tracker-39bca
firebase deploy --only functions --project fitness-tracker-39bca
