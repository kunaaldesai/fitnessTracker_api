import importlib
import logging
import unittest
from datetime import date, datetime, timedelta, timezone

from utils import InMemoryFirestore, ensure_functions_on_path, install_fake_firebase

ensure_functions_on_path()
_, fake_auth = install_fake_firebase(InMemoryFirestore())

fitness_routes = importlib.import_module("routes.fitness")


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


class FitnessApiTestCase(unittest.TestCase):
    def setUp(self):
        self.db = InMemoryFirestore()
        fitness_routes.db = self.db
        fake_auth.verify_id_token.reset_mock()
        fake_auth.verify_id_token.side_effect = None
        fake_auth.verify_id_token.return_value = {
            "uid": "user-1",
            "email": "user@example.com",
            "name": "Ada Lovelace",
        }
        self.app = fitness_routes.create_fitness_app()
        self.client = self.app.test_client()

    def auth_headers(self, token="valid-token"):
        return {"Authorization": f"Bearer {token}"}

    def test_missing_auth_is_rejected(self):
        response = self.client.get("/api/fitness/profile/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["status"], "error")

    def test_invalid_auth_is_rejected(self):
        fake_auth.verify_id_token.side_effect = ValueError("bad token")

        response = self.client.get("/api/fitness/profile/", headers=self.auth_headers("bad"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Invalid Firebase ID token.")

    def test_profile_get_returns_defaults_and_creates_user_doc(self):
        response = self.client.get("/api/fitness/profile/", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["user"]["uuid"], "user-1")
        self.assertEqual(data["profile"]["activity_level"], "sedentary")
        self.assertEqual(data["profile"]["bmr_formula"], "katch_mcardle")
        self.assertIn("body_fat_percent", data["missing_fields"]["bmr"])
        self.assertEqual(self.db.get_doc("users", "user-1")["uuid"], "user-1")

    def test_profile_post_saves_metrics_in_firestore(self):
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "1990-01-01",
            "sex_for_bmr": "female",
            "height_feet": 5,
            "height_inches": 7,
            "weight_lbs": 140,
            "activity_level": "moderately_active",
            "bmr_formula": "mifflin_st_jeor",
            "custom_goal_lbs_per_week": 0.5,
        }

        response = self.client.post("/api/fitness/profile/", json=payload, headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertGreater(data["metrics"]["bmi"], 0)
        self.assertGreater(data["metrics"]["bmr"], 0)
        self.assertGreater(data["metrics"]["tdee"], data["metrics"]["bmr"])
        user_doc = self.db.get_doc("users", "user-1")
        self.assertEqual(user_doc["first_name"], "Ada")
        self.assertEqual(user_doc["fitness_profile"]["activity_level"], "moderately_active")

    def test_profile_validation_error(self):
        response = self.client.post(
            "/api/fitness/profile/",
            json={"height_feet": 9, "height_inches": 0},
            headers=self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Height in feet", response.get_json()["error"])

    def test_profile_rejects_non_finite_numbers(self):
        response = self.client.post(
            "/api/fitness/profile/",
            json={"weight_lbs": "NaN"},
            headers=self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid weight", response.get_json()["error"])

    def test_profile_goal_validation_error(self):
        response = self.client.post(
            "/api/fitness/profile/",
            json={"target_weight_lbs": -10},
            headers=self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Target weight", response.get_json()["error"])

        response = self.client.post(
            "/api/fitness/profile/",
            json={"custom_goal_lbs_per_week": 3},
            headers=self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Custom goal", response.get_json()["error"])

    def test_weight_history_creates_baseline_once_from_existing_profile_weight(self):
        today = utc_today().isoformat()
        self.db.seed(
            "users",
            "user-1",
            {
                "uuid": "user-1",
                "uid": "user-1",
                "email": "user@example.com",
                "fitness_profile": {
                    "height_feet": 5,
                    "height_inches": 10,
                    "weight_lbs": 180,
                    "activity_level": "sedentary",
                    "bmr_formula": "mifflin_st_jeor",
                    "date_of_birth": "1990-01-01",
                    "sex_for_bmr": "male",
                    "weight_history_initialized": False,
                },
            },
        )

        response = self.client.get("/api/fitness/profile/weight-history/?range=all", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["date"], today)
        self.assertEqual(data["entries"][0]["weight_lbs"], 180)
        self.assertTrue(self.db.get_doc("users", "user-1")["fitness_profile"]["weight_history_initialized"])

        self.client.post(
            f"/api/fitness/profile/weight-history/{today}/delete/",
            headers=self.auth_headers(),
        )
        response = self.client.get("/api/fitness/profile/weight-history/?range=all", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["entries"], [])

    def test_weight_entry_crud_converts_kg_upserts_and_syncs_latest_profile_weight(self):
        first = self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_kg": 80, "note": "Morning"},
            headers=self.auth_headers(),
        )

        self.assertEqual(first.status_code, 200)
        entry = first.get_json()["entry"]
        self.assertEqual(entry["date"], "2026-06-01")
        self.assertAlmostEqual(entry["weight_lbs"], 176.37)
        self.assertEqual(entry["source_unit"], "kg")
        self.assertAlmostEqual(self.db.get_doc("users", "user-1")["fitness_profile"]["weight_lbs"], 176.37)

        second = self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_kg": 81},
            headers=self.auth_headers(),
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.get_json()["weight_history"]["entries"]), 1)
        self.assertAlmostEqual(second.get_json()["entry"]["weight_lbs"], 178.57)

    def test_weight_entry_update_date_conflict_and_delete_latest_sync(self):
        self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_lbs": 180},
            headers=self.auth_headers(),
        )
        self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-02", "weight_lbs": 181},
            headers=self.auth_headers(),
        )

        conflict = self.client.post(
            "/api/fitness/profile/weight-history/2026-06-01/update/",
            json={"date": "2026-06-02", "weight_lbs": 182},
            headers=self.auth_headers(),
        )
        self.assertEqual(conflict.status_code, 400)
        self.assertIn("already exists", conflict.get_json()["error"])

        moved = self.client.post(
            "/api/fitness/profile/weight-history/2026-06-01/update/",
            json={"date": "2026-06-03", "weight_lbs": 182},
            headers=self.auth_headers(),
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.get_json()["entry"]["date"], "2026-06-03")
        self.assertEqual(self.db.get_doc("users", "user-1")["fitness_profile"]["weight_lbs"], 182)

        delete_latest = self.client.post(
            "/api/fitness/profile/weight-history/2026-06-03/delete/",
            headers=self.auth_headers(),
        )
        self.assertEqual(delete_latest.status_code, 200)
        self.assertEqual(self.db.get_doc("users", "user-1")["fitness_profile"]["weight_lbs"], 181)

        self.client.post(
            "/api/fitness/profile/weight-history/2026-06-02/delete/",
            headers=self.auth_headers(),
        )
        self.assertEqual(self.db.get_doc("users", "user-1")["fitness_profile"]["weight_lbs"], 181)

    def test_weight_history_includes_metrics_and_goal_projection(self):
        profile_payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "1990-01-01",
            "sex_for_bmr": "female",
            "height_feet": 5,
            "height_inches": 7,
            "weight_lbs": 150,
            "activity_level": "moderately_active",
            "bmr_formula": "mifflin_st_jeor",
            "target_weight_lbs": 140,
            "custom_goal_lbs_per_week": -1,
        }
        self.client.post("/api/fitness/profile/", json=profile_payload, headers=self.auth_headers())
        self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_lbs": 152},
            headers=self.auth_headers(),
        )
        self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-08", "weight_lbs": 150},
            headers=self.auth_headers(),
        )

        response = self.client.get("/api/fitness/profile/weight-history/?range=all", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertGreaterEqual(len(data["chart_points"]), 2)
        self.assertGreater(data["chart_points"][0]["bmi"], 0)
        self.assertGreater(data["chart_points"][0]["bmr"], 0)
        self.assertGreater(data["chart_points"][0]["tdee"], data["chart_points"][0]["bmr"])
        self.assertEqual(data["goal"]["target_weight_lbs"], 140)
        self.assertEqual(data["summary"]["target_delta_lbs"], -10)
        self.assertIsNotNone(data["goal"]["estimated_goal_date"])

    def test_weight_history_rejects_future_and_invalid_weights(self):
        future = (utc_today() + timedelta(days=1)).isoformat()

        response = self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": future, "weight_lbs": 180},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("future", response.get_json()["error"])

        response = self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_lbs": 0},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("positive", response.get_json()["error"])

        response = self.client.post(
            "/api/fitness/profile/weight-history/create/",
            json={"date": "2026-06-01", "weight_lbs": "Infinity"},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid weight", response.get_json()["error"])

        response = self.client.get(
            "/api/fitness/profile/weight-history/?start_date=not-a-date",
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid start date", response.get_json()["error"])

        response = self.client.get(
            f"/api/fitness/profile/weight-history/?end_date={future}",
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("future", response.get_json()["error"])

    def test_exercise_crud_day_records_analytics_history_calendar(self):
        create_response = self.client.post(
            "/api/fitness/exercises/create/",
            json={
                "owner_uuid": "attacker",
                "name": "Bench Press",
                "category": "Chest",
                "workout_date": "2026-06-01",
                "sets": [{"weight": 100, "reps": 10, "rpe": 8}],
            },
            headers=self.auth_headers(),
        )
        self.assertEqual(create_response.status_code, 200)
        exercise = create_response.get_json()["exercise"]
        exercise_id = exercise["id"]
        self.assertEqual(exercise["owner_uuid"], "user-1")
        self.assertEqual(exercise["total_volume"], 1000)
        self.assertEqual(list(self.db.collection("fitness_exercises").stream()), [])
        entry_doc = self.db.get_doc("users/user-1/workout_days/2026-06-01/exercise_entries", exercise_id)
        self.assertEqual(entry_doc["uid"], "user-1")
        self.assertEqual(entry_doc["entry_id"], exercise_id)
        self.assertEqual(entry_doc["schema_version"], 2)
        self.assertEqual(entry_doc["name_key"], "bench press")
        day_doc = self.db.get_doc("users/user-1/workout_days", "2026-06-01")
        self.assertEqual(day_doc["exercise_count"], 1)
        self.assertEqual(day_doc["category_counts"], {"Chest": 1})

        update_response = self.client.post(
            f"/api/fitness/exercises/{exercise_id}/update/",
            json={"sets": [{"weight": 105, "reps": 8, "rpe": 8.5}], "notes": "felt good"},
            headers=self.auth_headers(),
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["exercise"]["notes"], "felt good")
        self.assertEqual(
            self.db.get_doc("users/user-1/workout_days/2026-06-01/exercise_entries", exercise_id)["total_volume"],
            840,
        )
        record_doc = self.db.get_doc("users/user-1/exercise_records", "bench press")
        self.assertEqual(record_doc["exercise_name"], "Bench Press")
        self.assertEqual(record_doc["max_volume"], 840)

        day_response = self.client.get(
            "/api/fitness/day/?date=2026-06-01",
            headers=self.auth_headers(),
        )
        self.assertEqual(day_response.status_code, 200)
        self.assertEqual(day_response.get_json()["summary"]["exercise_count"], 1)
        self.assertEqual(day_response.get_json()["summary"]["total_volume"], 840)

        original_collection_group = self.db.collection_group
        self.db.collection_group = lambda name: (_ for _ in ()).throw(AssertionError("unexpected collection group query"))
        try:
            records_response = self.client.get("/api/fitness/records/?range=all", headers=self.auth_headers())
            self.assertEqual(records_response.status_code, 200)
            self.assertEqual(records_response.get_json()["records"][0]["exercise_name"], "Bench Press")

            analytics_response = self.client.get("/api/fitness/analytics/?range=all", headers=self.auth_headers())
            self.assertEqual(analytics_response.status_code, 200)
            self.assertEqual(analytics_response.get_json()["summary"]["total_volume"], 840)
            self.assertEqual(analytics_response.get_json()["muscle_split"][0]["group"], "Chest")
        finally:
            self.db.collection_group = original_collection_group

        history_response = self.client.get(
            "/api/fitness/exercise-history/?name=Bench%20Press",
            headers=self.auth_headers(),
        )
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.get_json()["session_count"], 1)

        calendar_response = self.client.get(
            "/api/fitness/workout-calendar/?range=all",
            headers=self.auth_headers(),
        )
        self.assertEqual(calendar_response.status_code, 200)
        self.assertEqual(calendar_response.get_json()["total_workout_days"], 1)

        huge_calendar_response = self.client.get(
            "/api/fitness/workout-calendar/?start_date=0001-01-01&end_date=9999-12-31",
            headers=self.auth_headers(),
        )
        self.assertEqual(huge_calendar_response.status_code, 400)
        self.assertIn("calendar range", huge_calendar_response.get_json()["error"])

        delete_response = self.client.post(
            f"/api/fitness/exercises/{exercise_id}/delete/",
            headers=self.auth_headers(),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json()["deleted"], True)
        self.assertEqual(self.db.get_doc("users/user-1/workout_days", "2026-06-01"), {})
        self.assertEqual(self.db.get_doc("users/user-1/exercise_records", "bench press"), {})
        self.assertEqual(self.db.get_doc("users/user-1/exercise_definitions", "bench press"), {})

    def test_exercise_options_include_default_and_custom(self):
        self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Custom Press", "category": "Shoulders", "workout_date": "2026-06-01"},
            headers=self.auth_headers(),
        )

        response = self.client.get("/api/fitness/exercise-options/", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        names = {row["name"] for row in payload["exercises"]}
        option_by_name = {row["name"]: row for row in payload["exercises"]}
        self.assertIn("Flat Dumbbell Bench Press", names)
        self.assertIn("Custom Press", names)
        self.assertEqual(option_by_name["Custom Press"]["session_count"], 1)
        self.assertEqual(option_by_name["Custom Press"]["last_workout_date"], "2026-06-01")
        self.assertEqual(option_by_name["Custom Press"]["last_workout_date_label"], "Jun 1, 2026")
        self.assertEqual(option_by_name["Flat Dumbbell Bench Press"]["session_count"], 0)
        self.assertIn("Forearms", payload["categories"])
        self.assertIn("Calves", payload["categories"])
        self.assertIn("Adductors", payload["categories"])
        self.assertIn("Stretching", payload["types"])
        self.assertIn("Hamstring Stretch", names)
        self.assertIn("Barbell Bench Press", names)
        self.assertIn("Elliptical", names)
        self.assertIn("Pigeon Pose", names)
        self.assertGreaterEqual(payload["default_count"], 250)
        self.assertEqual(self.db.get_doc("exercise_catalog", "flat dumbbell bench press")["source"], "default")
        self.assertEqual(self.db.get_doc("users/user-1/exercise_definitions", "custom press")["source"], "custom")

    def test_custom_exercise_options_are_scoped_to_current_user(self):
        def auth_for_token(token):
            if token == "user-2-token":
                return {"uid": "user-2", "email": "user2@example.com", "name": "User Two"}
            return {"uid": "user-1", "email": "user1@example.com", "name": "User One"}

        fake_auth.verify_id_token.side_effect = auth_for_token

        create_response = self.client.post(
            "/api/fitness/exercises/create/",
            json={
                "name": "Private Joke Lift",
                "category": "Back",
                "movement_type": "Strength",
                "workout_date": "2026-06-01",
            },
            headers=self.auth_headers("user-1-token"),
        )
        self.assertEqual(create_response.status_code, 200)

        user_one_response = self.client.get(
            "/api/fitness/exercise-options/",
            headers=self.auth_headers("user-1-token"),
        )
        self.assertEqual(user_one_response.status_code, 200)
        user_one_names = {row["name"] for row in user_one_response.get_json()["exercises"]}
        self.assertIn("Private Joke Lift", user_one_names)

        user_two_response = self.client.get(
            "/api/fitness/exercise-options/",
            headers=self.auth_headers("user-2-token"),
        )
        self.assertEqual(user_two_response.status_code, 200)
        user_two_names = {row["name"] for row in user_two_response.get_json()["exercises"]}
        self.assertIn("Flat Dumbbell Bench Press", user_two_names)
        self.assertNotIn("Private Joke Lift", user_two_names)

        self.assertEqual(self.db.get_doc("exercise_catalog", "private joke lift"), {})
        self.assertEqual(
            self.db.get_doc("users/user-1/exercise_definitions", "private joke lift")["source"],
            "custom",
        )
        self.assertEqual(self.db.get_doc("users/user-2/exercise_definitions", "private joke lift"), {})

    def test_cardio_and_stretching_sets_use_effort_fields(self):
        cardio_response = self.client.post(
            "/api/fitness/exercises/create/",
            json={
                "name": "Jump Rope",
                "category": "Cardio",
                "movement_type": "Cardio",
                "workout_date": "2026-06-01",
                "sets": [{"duration_seconds": 600, "distance_miles": 0.5, "rpe": 7}],
            },
            headers=self.auth_headers(),
        )
        self.assertEqual(cardio_response.status_code, 200)
        cardio = cardio_response.get_json()["exercise"]
        self.assertEqual(cardio["movement_type"], "Cardio")
        self.assertEqual(cardio["completed_sets"], 1)
        self.assertEqual(cardio["total_volume"], 0)
        self.assertEqual(cardio["total_duration_seconds"], 600)
        self.assertEqual(cardio["total_distance_miles"], 0.5)

        stretch_response = self.client.post(
            "/api/fitness/exercises/create/",
            json={
                "name": "Hamstring Stretch",
                "category": "Hamstrings",
                "movement_type": "Stretching",
                "workout_date": "2026-06-01",
                "sets": [{"duration_seconds": 45, "side": "Left", "rpe": 3}],
            },
            headers=self.auth_headers(),
        )
        self.assertEqual(stretch_response.status_code, 200)
        stretch = stretch_response.get_json()["exercise"]
        self.assertEqual(stretch["movement_type"], "Stretching")
        self.assertEqual(stretch["sets"][0]["side"], "Left")
        self.assertEqual(stretch["completed_sets"], 1)
        self.assertEqual(stretch["total_duration_seconds"], 45)

        day_response = self.client.get("/api/fitness/day/?date=2026-06-01", headers=self.auth_headers())
        self.assertEqual(day_response.get_json()["summary"]["sets_completed"], 2)
        self.assertEqual(day_response.get_json()["summary"]["total_volume"], 0)
        day_doc = self.db.get_doc("users/user-1/workout_days", "2026-06-01")
        self.assertEqual(day_doc["type_counts"], {"Cardio": 1, "Stretching": 1})
        self.assertEqual(day_doc["total_duration_seconds"], 645)

    def test_exercise_update_can_move_nested_entry_between_days(self):
        created = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Squat", "category": "Quads", "workout_date": "2026-06-01", "sets": [{"weight": 200, "reps": 5}]},
            headers=self.auth_headers(),
        ).get_json()["exercise"]

        moved = self.client.post(
            f"/api/fitness/exercises/{created['id']}/update/",
            json={"workout_date": "2026-06-02"},
            headers=self.auth_headers(),
        )

        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.get_json()["exercise"]["id"], created["id"])
        self.assertEqual(self.db.get_doc("users/user-1/workout_days/2026-06-01/exercise_entries", created["id"]), {})
        self.assertEqual(self.db.get_doc("users/user-1/workout_days", "2026-06-01"), {})
        self.assertEqual(
            self.db.get_doc("users/user-1/workout_days/2026-06-02/exercise_entries", created["id"])["workout_date"],
            "2026-06-02",
        )

    def test_exercise_set_limits_are_enforced(self):
        too_many_sets = [{"weight": 100, "reps": 5} for _ in range(41)]
        response = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Bench Press", "workout_date": "2026-06-01", "sets": too_many_sets},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 40 sets", response.get_json()["error"])

        response = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Bench Press", "workout_date": "2026-06-01", "sets": [{"weight": 2001, "reps": 5}]},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Set weight", response.get_json()["error"])

        response = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Bench Press", "workout_date": "2026-06-01", "sets": [{"weight": 100, "reps": 1001}]},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Set reps", response.get_json()["error"])

    def test_reorder_previous_last_sessions_and_copy(self):
        first = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Squat", "category": "Quads", "workout_date": "2026-06-01", "sets": [{"weight": 200, "reps": 5}]},
            headers=self.auth_headers(),
        ).get_json()["exercise"]
        second = self.client.post(
            "/api/fitness/exercises/create/",
            json={"name": "Row", "category": "Back", "workout_date": "2026-06-01", "sets": [{"weight": 120, "reps": 8}]},
            headers=self.auth_headers(),
        ).get_json()["exercise"]

        reorder_response = self.client.post(
            "/api/fitness/exercises/reorder/",
            json={"workout_date": "2026-06-01", "order": [second["id"], first["id"]]},
            headers=self.auth_headers(),
        )
        self.assertEqual(reorder_response.status_code, 200)

        day_response = self.client.get("/api/fitness/day/?date=2026-06-01", headers=self.auth_headers())
        self.assertEqual([row["name"] for row in day_response.get_json()["exercises"]], ["Row", "Squat"])

        previous_response = self.client.get(
            "/api/fitness/exercises/previous-workout/?before=2026-06-02",
            headers=self.auth_headers(),
        )
        self.assertEqual(previous_response.status_code, 200)
        self.assertEqual(previous_response.get_json()["previous_date"], "2026-06-01")

        copy_response = self.client.post(
            "/api/fitness/exercises/copy-from-date/",
            json={"source_date": "2026-06-01", "target_date": "2026-06-02"},
            headers=self.auth_headers(),
        )
        self.assertEqual(copy_response.status_code, 200)
        self.assertEqual(copy_response.get_json()["count"], 2)

        last_sessions_response = self.client.get(
            "/api/fitness/exercises/last-sessions/?date=2026-06-02",
            headers=self.auth_headers(),
        )
        self.assertEqual(last_sessions_response.status_code, 200)
        self.assertIn("Squat", last_sessions_response.get_json()["last_sessions"])

        oversized_copy = self.client.post(
            "/api/fitness/exercises/copy-from-date/",
            json={"target_date": "2026-06-03", "exercise_ids": [f"ex-{index}" for index in range(76)]},
            headers=self.auth_headers(),
        )
        self.assertEqual(oversized_copy.status_code, 400)
        self.assertIn("copy at most 75", oversized_copy.get_json()["error"])

    def test_ownership_is_enforced(self):
        self.db.seed(
            "fitness_exercises",
            "other-ex",
            {
                "owner_uuid": "other-user",
                "workout_date": "2026-06-01",
                "order_index": 0,
                "name": "Secret Lift",
                "category": "Back",
                "movement_type": "Strength",
                "sets": [{"weight": 100, "reps": 5, "rpe": None}],
            },
        )
        self.db.seed(
            "users/other-user/workout_days/2026-06-01/exercise_entries",
            "other-v2",
            {
                "uid": "other-user",
                "owner_uuid": "other-user",
                "entry_id": "other-v2",
                "workout_date": "2026-06-01",
                "day_id": "2026-06-01",
                "order_index": 0,
                "name": "Secret V2 Lift",
                "name_key": "secret v2 lift",
                "category": "Back",
                "category_key": "back",
                "movement_type": "Strength",
                "movement_type_key": "strength",
                "sets": [{"weight": 100, "reps": 5, "rpe": None}],
                "schema_version": 2,
            },
        )

        response = self.client.post(
            "/api/fitness/exercises/other-ex/update/",
            json={"notes": "steal"},
            headers=self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Exercise not found.")
        self.assertNotEqual(self.db.get_doc("fitness_exercises", "other-ex").get("notes"), "steal")

        response = self.client.post(
            "/api/fitness/exercises/other-v2/update/",
            json={"notes": "steal"},
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Exercise not found.")
        self.assertNotEqual(
            self.db.get_doc("users/other-user/workout_days/2026-06-01/exercise_entries", "other-v2").get("notes"),
            "steal",
        )

    def test_internal_errors_do_not_leak_details(self):
        fitness_routes.db = BrokenDb()
        app = fitness_routes.create_fitness_app()
        client = app.test_client()

        logging.disable(logging.CRITICAL)
        try:
            response = client.get("/api/fitness/profile/", headers=self.auth_headers())
        finally:
            logging.disable(logging.NOTSET)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "Unable to process Logmaxxing request right now.")


class BrokenDb:
    def collection(self, name):
        raise RuntimeError("database host 10.0.0.4 unreachable")


if __name__ == "__main__":
    unittest.main()
