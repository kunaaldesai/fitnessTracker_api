import os
import sys
import types
from unittest.mock import MagicMock

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FUNCTIONS_DIR = os.path.join(ROOT_DIR, "functions")


def ensure_functions_on_path():
    if FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, FUNCTIONS_DIR)


def install_fake_firebase(fake_db):
    fake_firestore = types.SimpleNamespace(
        SERVER_TIMESTAMP="SERVER_TIMESTAMP",
        Query=types.SimpleNamespace(DESCENDING="DESCENDING"),
    )
    fake_firebase_admin = types.SimpleNamespace(
        _apps=["test-app"],
        initialize_app=MagicMock(),
        credentials=types.SimpleNamespace(ApplicationDefault=MagicMock()),
        firestore=fake_firestore,
    )
    sys.modules["firebase_admin"] = fake_firebase_admin
    sys.modules["firebase_admin.credentials"] = fake_firebase_admin.credentials
    sys.modules["firebase_admin.firestore"] = fake_firestore

    config_pkg = types.ModuleType("config")
    db_module = types.ModuleType("config.db")
    db_module.db = fake_db
    sys.modules["config"] = config_pkg
    sys.modules["config.db"] = db_module

    return fake_firestore


def make_doc(doc_id="doc1", data=None, exists=True):
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def make_doc_with_reference(doc_id="doc1", data=None):
    doc = make_doc(doc_id=doc_id, data=data, exists=True)
    doc.reference = MagicMock()
    return doc
