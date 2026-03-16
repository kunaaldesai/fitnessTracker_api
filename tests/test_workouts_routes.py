import sys
import unittest
from unittest.mock import MagicMock, patch

from utils import ensure_functions_on_path, install_fake_firebase, make_doc, make_doc_with_reference

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib

workouts_routes = importlib.import_module("routes.workouts")
workouts_helpers = importlib.import_module("helpers.workouts_helpers")


class WorkoutsRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        workouts_routes.db = self.fake_db
        workouts_helpers.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = workouts_routes.create_workouts_app()
        self.client = self.app.test_client()

    def test_create_exercise_success(self):
        users_collection = MagicMock()
        user_doc = MagicMock()
        exercises_collection = MagicMock()
        exercise_ref = MagicMock()
        exercise_ref.id = "ex1"

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = exercises_collection
        exercises_collection.document.return_value = exercise_ref

        response = self.client.post("/users/user1/exercises", json={"name": "Bench"})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["id"], "ex1")
        exercise_ref.set.assert_called_once()

    def test_create_exercise_requires_name(self):
        response = self.client.post("/users/user1/exercises", json={})

        self.assertEqual(response.status_code, 400)

    def test_get_exercises_success(self):
        exercises_collection = MagicMock()
        query = MagicMock()
        self.fake_db.collection.return_value.document.return_value.collection.return_value = exercises_collection
        exercises_collection.where.return_value = query

        doc1 = make_doc("ex1", {"name": "Bench", "archived": False})
        query.stream.return_value = [doc1]

        response = self.client.get("/users/user1/exercises")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "ex1")

    def test_get_exercise_detail_success(self):
        users_collection = MagicMock()
        user_doc = MagicMock()
        exercises_collection = MagicMock()
        exercise_ref = MagicMock()
        exercise_doc = make_doc("ex1", {"name": "Bench"})
        exercise_ref.get.return_value = exercise_doc

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = exercises_collection
        exercises_collection.document.return_value = exercise_ref

        response = self.client.get("/users/user1/exercises/ex1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "ex1")

    def test_update_exercise_success(self):
        users_collection = MagicMock()
        user_doc = MagicMock()
        exercises_collection = MagicMock()
        exercise_ref = MagicMock()
        exercise_doc = make_doc("ex1", {"name": "Bench"})
        exercise_ref.get.return_value = exercise_doc

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = exercises_collection
        exercises_collection.document.return_value = exercise_ref

        response = self.client.put("/users/user1/exercises/ex1", json={"notes": "New"})

        self.assertEqual(response.status_code, 200)
        exercise_ref.update.assert_called_once()

    def test_delete_exercise_success(self):
        users_collection = MagicMock()
        user_doc = MagicMock()
        exercises_collection = MagicMock()
        exercise_ref = MagicMock()
        exercise_doc = make_doc("ex1", {"name": "Bench"})
        exercise_ref.get.return_value = exercise_doc

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = exercises_collection
        exercises_collection.document.return_value = exercise_ref

        response = self.client.delete("/users/user1/exercises/ex1")

        self.assertEqual(response.status_code, 200)
        exercise_ref.delete.assert_called_once()

    def test_create_workout_success(self):
        users_collection = MagicMock()
        user_doc = MagicMock()
        workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout1"

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = workouts_collection
        workouts_collection.document.return_value = workout_ref

        response = self.client.post("/users/user1/workouts", json={"notes": "Leg day"})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["id"], "workout1")
        workout_ref.set.assert_called_once()

    def test_get_workouts_success(self):
        workouts_collection = MagicMock()
        ordered_query = MagicMock()
        self.fake_db.collection.return_value.document.return_value.collection.return_value = workouts_collection
        workouts_collection.order_by.return_value = ordered_query

        doc1 = make_doc("workout1", {"date": "2024-01-10"})
        ordered_query.stream.return_value = [doc1]

        response = self.client.get("/users/user1/workouts")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "workout1")

    def test_workout_detail_update_success(self):
        workout_ref = MagicMock()
        workout_doc = make_doc("workout1", {"date": "2024-01-10"})

        with patch.object(workouts_routes, "get_workout_ref", return_value=(workout_ref, workout_doc)):
            response = self.client.put("/users/user1/workouts/workout1", json={"notes": "Updated"})

        self.assertEqual(response.status_code, 200)
        workout_ref.update.assert_called_once()

    def test_workout_detail_delete_success(self):
        # Updated to test simple deletion
        workout_ref = MagicMock()
        workout_doc = make_doc("workout1", {"date": "2024-01-10"})

        with patch.object(workouts_routes, "get_workout_ref", return_value=(workout_ref, workout_doc)):
            response = self.client.delete("/users/user1/workouts/workout1")

        self.assertEqual(response.status_code, 200)
        workout_ref.delete.assert_called_once()

    def test_get_workout_success(self):
        workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_doc = make_doc("workout1", {"name": "Template"})
        workout_ref.get.return_value = workout_doc
        workouts_collection.document.return_value = workout_ref

        self.fake_db.collection.return_value = workouts_collection

        response = self.client.get("/getWorkout/workout1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "workout1")

    def test_get_all_workouts_success(self):
        workouts_collection = MagicMock()
        doc1 = make_doc("workout1", {"name": "Template"})
        workouts_collection.stream.return_value = [doc1]
        self.fake_db.collection.return_value = workouts_collection

        response = self.client.get("/getAllWorkouts")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "workout1")

    def test_create_workout_template_success(self):
        workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout1"
        workouts_collection.document.return_value = workout_ref
        self.fake_db.collection.return_value = workouts_collection

        response = self.client.post("/createWorkout", json={"name": "Template"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "workout1")


if __name__ == "__main__":
    unittest.main()
