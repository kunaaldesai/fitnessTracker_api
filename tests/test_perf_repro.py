import sys
import unittest
from unittest.mock import MagicMock, patch

from utils import ensure_functions_on_path, install_fake_firebase, make_doc

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib

workouts_routes = importlib.import_module("routes.workouts")
workouts_helpers = importlib.import_module("helpers.workouts_helpers")

class WorkoutsPerformanceTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        workouts_routes.db = self.fake_db
        workouts_helpers.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = workouts_routes.create_workouts_app()
        self.client = self.app.test_client()

    def test_start_workout_n_plus_one_behavior(self):
        workouts_collection = MagicMock()
        users_collection = MagicMock()

        # Template with 2 exercises needing name lookup
        template_exercises = [
            {"exerciseId": "ex1"}, # Missing name
            {"exerciseId": "ex2", "name": "Squat"}, # Has name
            {"exerciseId": "ex3"}  # Missing name
        ]
        template_ref = MagicMock()
        template_doc = make_doc("template1", {"exercises": template_exercises})
        template_ref.get.return_value = template_doc
        workouts_collection.document.return_value = template_ref

        user_doc = MagicMock()
        user_workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout1"
        item_collection = MagicMock()
        item_ref = MagicMock()

        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = user_workouts_collection
        user_workouts_collection.document.return_value = workout_ref
        workout_ref.collection.return_value = item_collection
        item_collection.document.return_value = item_ref

        exercises_collection = MagicMock()

        # Setup side_effect for user_doc.collection("exercises")
        def user_collection_side_effect(name):
            if name == "workouts": return user_workouts_collection
            if name == "exercises": return exercises_collection
            return MagicMock()

        user_doc.collection.side_effect = user_collection_side_effect

        ex1_doc = make_doc("ex1", {"name": "Bench Press"})
        ex3_doc = make_doc("ex3", {"name": "Deadlift"})

        # Determine which exercise ref is being requested and return appropriate mock with get()
        def exercise_document_side_effect(id):
            doc_ref = MagicMock()
            doc_ref.id = id
            # We don't expect .get() to be called on these refs in the optimized path,
            # but if it is, it should return the doc.
            if id == "ex1":
                doc_ref.get.return_value = ex1_doc
            elif id == "ex3":
                doc_ref.get.return_value = ex3_doc
            else:
                doc_ref.get.return_value = make_doc(id, {}, exists=False)
            return doc_ref

        exercises_collection.document.side_effect = exercise_document_side_effect

        # Mock db.get_all
        def get_all_side_effect(refs):
            docs = []
            for ref in refs:
                if ref.id == "ex1":
                    docs.append(ex1_doc)
                elif ref.id == "ex3":
                    docs.append(ex3_doc)
                else:
                    docs.append(make_doc(ref.id, {}, exists=False))
            return docs

        self.fake_db.get_all.side_effect = get_all_side_effect

        self.fake_db.collection.side_effect = lambda name: workouts_collection if name == "workouts" else users_collection
        batch = MagicMock()
        self.fake_db.batch.return_value = batch

        # Call the endpoint
        response = self.client.post("/users/user1/workouts/start", json={"workout_id": "template1"})

        self.assertEqual(response.status_code, 200)

        # Verify that db.get_all was called
        self.assertTrue(self.fake_db.get_all.called, "db.get_all should be called for optimization")

        # Verify correct args passed to get_all
        call_args = self.fake_db.get_all.call_args[0][0]
        called_ids_in_batch = sorted([ref.id for ref in call_args])
        self.assertEqual(called_ids_in_batch, ["ex1", "ex3"])

        # Verify that document() was called to create refs
        calls = exercises_collection.document.call_args_list
        called_ids = [call[0][0] for call in calls]
        self.assertIn("ex1", called_ids)
        self.assertIn("ex3", called_ids)
