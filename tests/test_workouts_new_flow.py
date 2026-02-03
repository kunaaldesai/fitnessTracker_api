import sys
import unittest
from unittest.mock import MagicMock, patch

from utils import ensure_functions_on_path, install_fake_firebase, make_doc

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib

# Reload modules to ensure patches are applied if needed
workouts_routes = importlib.import_module("routes.workouts")
workouts_helpers = importlib.import_module("helpers.workouts_helpers")

class WorkoutsNewFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        workouts_routes.db = self.fake_db
        workouts_helpers.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = workouts_routes.create_workouts_app()
        self.client = self.app.test_client()

    @patch("routes.workouts.process_workout_exercises")
    def test_create_workout_nested_success(self, mock_process):
        # Setup mocks
        users_collection = MagicMock()
        user_doc = MagicMock()
        workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout_new_1"

        self.fake_db.collection.return_value = users_collection
        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = workouts_collection
        workouts_collection.document.return_value = workout_ref

        # Mock helper return
        mock_process.return_value = [{"exerciseId": "ex1", "sets": [{"reps": 10}]}]

        # Payload
        payload = {
            "date": "2024-01-01",
            "exercises": [
                {"exerciseId": "ex1", "sets": [{"reps": 10}]}
            ]
        }

        # Call
        response = self.client.post("/users/user1/workouts", json=payload)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "workout_new_1")

        # Verify helper called
        mock_process.assert_called_once()
        args, _ = mock_process.call_args
        self.assertEqual(args[0], "user1")
        self.assertEqual(args[1], "workout_new_1")
        self.assertEqual(len(args[2]), 1)

        # Verify DB Save
        workout_ref.set.assert_called_once()
        saved_data = workout_ref.set.call_args[0][0]
        self.assertIn("exercises", saved_data)
        self.assertEqual(saved_data["exercises"], [{"exerciseId": "ex1", "sets": [{"reps": 10}]}])

    @patch("routes.workouts.process_workout_exercises")
    def test_update_workout_nested_success(self, mock_process):
        # Setup mocks
        workout_ref = MagicMock()
        workout_doc = make_doc("workout_1", {"date": "2024-01-01"})

        # We need to mock get_workout_ref used in the route
        with patch("routes.workouts.get_workout_ref", return_value=(workout_ref, workout_doc)):
            # Mock helper return
            mock_process.return_value = [{"exerciseId": "ex1", "sets": [{"reps": 12}]}]

            # Payload
            payload = {
                "exercises": [
                    {"exerciseId": "ex1", "sets": [{"reps": 12}]}
                ]
            }

            # Call
            response = self.client.put("/users/user1/workouts/workout_1", json=payload)

            # Assert
            self.assertEqual(response.status_code, 200)

            # Verify helper called
            mock_process.assert_called_once()

            # Verify DB Update
            workout_ref.update.assert_called_once()
            updated_data = workout_ref.update.call_args[0][0]
            self.assertIn("exercises", updated_data)
            self.assertEqual(updated_data["exercises"], [{"exerciseId": "ex1", "sets": [{"reps": 12}]}])

    def test_get_workout_direct_return(self):
        # Verify GET returns the doc directly without fetching subcollections
        workout_ref = MagicMock()
        # Doc has nested exercises
        workout_data = {
            "date": "2024-01-01",
            "exercises": [{"exerciseId": "ex1", "sets": []}]
        }
        workout_doc = make_doc("workout_1", workout_data)

        with patch("routes.workouts.get_workout_ref", return_value=(workout_ref, workout_doc)):
            # We don't need to mock attach_sets because it shouldn't be called
            response = self.client.get("/users/user1/workouts/workout_1")

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["id"], "workout_1")
            self.assertEqual(data["exercises"], [{"exerciseId": "ex1", "sets": []}])

            # Ensure no subcollection calls (collection() shouldn't be called on ref)
            workout_ref.collection.assert_not_called()

    @patch("helpers.workouts_helpers.update_pr_if_needed")
    def test_process_workout_exercises_integration(self, mock_update_pr):
        # Test the helper logic specifically
        from helpers.workouts_helpers import process_workout_exercises

        exercises_data = [
            {
                "exerciseId": "ex1",
                "sets": [
                    {"reps": 10, "weight": 100, "rir": 2} # should verify derived fields
                ]
            }
        ]

        processed = process_workout_exercises("user1", "workout1", exercises_data)

        self.assertEqual(len(processed), 1)
        processed_set = processed[0]["sets"][0]

        # Verify derived fields
        self.assertEqual(processed_set["volume"], 1000.0)
        self.assertEqual(processed_set["rpe"], 8.0) # 10 - 2

        # Verify PR check
        mock_update_pr.assert_called_once()
        _, kwargs = mock_update_pr.call_args
        self.assertEqual(kwargs["user_id"], "user1")
        self.assertEqual(kwargs["exercise_id"], "ex1")
        self.assertEqual(kwargs["workout_id"], "workout1")

if __name__ == "__main__":
    unittest.main()
