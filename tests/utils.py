import os
import sys
import types
import copy
from unittest.mock import MagicMock

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FUNCTIONS_DIR = os.path.join(ROOT_DIR, "functions")


def ensure_functions_on_path():
    if FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, FUNCTIONS_DIR)


def install_fake_firebase(fake_db):
    fake_auth = types.SimpleNamespace(verify_id_token=MagicMock())
    fake_firestore = types.SimpleNamespace(
        SERVER_TIMESTAMP="SERVER_TIMESTAMP",
        Query=types.SimpleNamespace(DESCENDING="DESCENDING"),
    )
    fake_firebase_admin = types.SimpleNamespace(
        _apps=["test-app"],
        initialize_app=MagicMock(),
        credentials=types.SimpleNamespace(ApplicationDefault=MagicMock()),
        firestore=fake_firestore,
        auth=fake_auth,
    )
    sys.modules["firebase_admin"] = fake_firebase_admin
    sys.modules["firebase_admin.credentials"] = fake_firebase_admin.credentials
    sys.modules["firebase_admin.firestore"] = fake_firestore
    sys.modules["firebase_admin.auth"] = fake_auth

    config_pkg = types.ModuleType("config")
    db_module = types.ModuleType("config.db")
    db_module.db = fake_db
    sys.modules["config"] = config_pkg
    sys.modules["config.db"] = db_module

    return fake_firestore, fake_auth


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


class InMemoryDocumentSnapshot:
    def __init__(self, reference, data=None, exists=True):
        self.reference = reference
        self.id = reference.id
        self.exists = exists
        self._data = copy.deepcopy(data or {})

    def to_dict(self):
        return copy.deepcopy(self._data)


class InMemoryDocumentReference:
    def __init__(self, collection, doc_id):
        self._collection = collection
        self.id = doc_id

    def get(self):
        if self.id not in self._collection._docs:
            return InMemoryDocumentSnapshot(self, {}, exists=False)
        return InMemoryDocumentSnapshot(self, self._collection._docs[self.id], exists=True)

    def set(self, data, merge=False):
        if merge and self.id in self._collection._docs:
            current = copy.deepcopy(self._collection._docs[self.id])
            current.update(copy.deepcopy(data or {}))
            self._collection._docs[self.id] = current
        else:
            self._collection._docs[self.id] = copy.deepcopy(data or {})

    def update(self, data):
        if self.id not in self._collection._docs:
            self._collection._docs[self.id] = {}
        self._collection._docs[self.id].update(copy.deepcopy(data or {}))

    def delete(self):
        self._collection._docs.pop(self.id, None)


class InMemoryQuery:
    def __init__(self, collection, filters=None):
        self._collection = collection
        self._filters = list(filters or [])

    def where(self, *args, **kwargs):
        filter_obj = kwargs.get("filter")
        if filter_obj is not None:
            field = (
                getattr(filter_obj, "field_path", None)
                or getattr(filter_obj, "_field_path", None)
            )
            op = (
                getattr(filter_obj, "op_string", None)
                or getattr(filter_obj, "_op_string", None)
                or "=="
            )
            value = getattr(filter_obj, "value", None)
            if value is None and hasattr(filter_obj, "_value"):
                value = getattr(filter_obj, "_value")
        else:
            field = args[0]
            op = args[1]
            value = args[2]
        return InMemoryQuery(self._collection, [*self._filters, (field, op, value)])

    def stream(self):
        snapshots = []
        for doc_id, data in self._collection._docs.items():
            if self._matches(data):
                snapshots.append(
                    InMemoryDocumentSnapshot(
                        InMemoryDocumentReference(self._collection, doc_id),
                        data,
                        exists=True,
                    )
                )
        return snapshots

    def _matches(self, data):
        for field, op, value in self._filters:
            if op != "==":
                return False
            if data.get(field) != value:
                return False
        return True


class InMemoryCollectionReference(InMemoryQuery):
    def __init__(self, db, name):
        self._db = db
        self.name = name
        self._docs = db._collections.setdefault(name, {})
        super().__init__(self, [])

    def document(self, doc_id=None):
        if not doc_id:
            doc_id = f"doc_{self._db._next_id}"
            self._db._next_id += 1
        return InMemoryDocumentReference(self, str(doc_id))


class InMemoryBatch:
    def __init__(self):
        self._operations = []

    def set(self, ref, data, merge=False):
        self._operations.append(("set", ref, data, merge))

    def update(self, ref, data):
        self._operations.append(("update", ref, data, False))

    def delete(self, ref):
        self._operations.append(("delete", ref, None, False))

    def commit(self):
        for op, ref, data, merge in self._operations:
            if op == "set":
                ref.set(data, merge=merge)
            elif op == "update":
                ref.update(data)
            elif op == "delete":
                ref.delete()
        self._operations = []


class InMemoryFirestore:
    def __init__(self):
        self._collections = {}
        self._next_id = 1

    def collection(self, name):
        return InMemoryCollectionReference(self, name)

    def batch(self):
        return InMemoryBatch()

    def seed(self, collection, doc_id, data):
        self.collection(collection).document(doc_id).set(data)

    def get_doc(self, collection, doc_id):
        return self.collection(collection).document(doc_id).get().to_dict()
