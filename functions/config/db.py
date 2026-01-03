import firebase_admin
from firebase_admin import credentials, firestore

# Ensure Firebase is initialized only once
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)

# Create global Firestore client
db = firestore.client()