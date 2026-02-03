from config.db import db
from firebase_admin import firestore
import logging


def parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ["true", "1", "yes", "y", "t"]


def compute_rpe(rir_value, rpe_value):
    if rpe_value is not None:
        return rpe_value
    if rir_value is None:
        return None
    try:
        return max(1.0, 10 - float(rir_value))
    except (TypeError, ValueError):
        return None


def compute_volume(reps_value, weight_value):
    if reps_value is None or weight_value is None:
        return None
    try:
        return float(reps_value) * float(weight_value)
    except (TypeError, ValueError):
        return None


def get_workout_ref(user_id, workout_id):
    workout_ref = db.collection("users").document(user_id).collection("workouts").document(workout_id)
    workout_doc = workout_ref.get()
    if not workout_doc.exists:
        return None, None
    return workout_ref, workout_doc


def update_pr_if_needed(user_id, exercise_id, set_payload, workout_id, workout_exercise_id, set_id):
    try:
        if not exercise_id:
            return
        prs_ref = db.collection("users").document(user_id).collection("prs").document(exercise_id)
        existing = prs_ref.get()
        existing_data = existing.to_dict() if existing.exists else {}
        existing_weight = existing_data.get("weight", 0) or 0
        existing_reps = existing_data.get("reps", 0) or 0

        incoming_weight = set_payload.get("weight", 0) or 0
        incoming_reps = set_payload.get("reps", 0) or 0

        better_pr = bool(set_payload.get("isPR"))
        if not better_pr:
            if incoming_weight > existing_weight:
                better_pr = True
            elif incoming_weight == existing_weight and incoming_reps > existing_reps:
                better_pr = True

        if better_pr:
            pr_payload = {
                "exerciseId": exercise_id,
                "weight": incoming_weight,
                "reps": incoming_reps,
                "rir": set_payload.get("rir"),
                "rpe": set_payload.get("rpe"),
                "workoutId": workout_id,
                "workoutExerciseId": workout_exercise_id,
                "setId": set_id,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }

            if existing.exists and existing_data.get("createdAt"):
                pr_payload["createdAt"] = existing_data.get("createdAt")
            else:
                pr_payload["createdAt"] = firestore.SERVER_TIMESTAMP

            prs_ref.set(pr_payload, merge=True)
    except Exception as pr_error:
        raise pr_error


def process_workout_exercises(user_id, workout_id, exercises_data):
    """
    Iterates through exercises and sets, computes derived fields, and updates PRs.
    Returns the processed exercises list.
    """
    processed_exercises = []

    for exercise_index, exercise in enumerate(exercises_data):
        # Ensure exercise is a dict
        if not isinstance(exercise, dict):
            continue

        processed_exercise = exercise.copy()

        # Get Exercise ID
        exercise_id = processed_exercise.get("exerciseId") or processed_exercise.get("id")

        # Process Sets
        sets_data = processed_exercise.get("sets", [])
        processed_sets = []

        for set_index, set_item in enumerate(sets_data):
            if not isinstance(set_item, dict):
                continue

            processed_set = set_item.copy()

            # Generate IDs if missing (useful for referencing)
            if not processed_set.get("id"):
                processed_set["id"] = f"set_{exercise_index}_{set_index}"

            # Compute RPE/Volume
            rir_value = processed_set.get("rir")
            rpe_value = processed_set.get("rpe")
            reps_value = processed_set.get("reps")
            weight_value = processed_set.get("weight")

            processed_set["rpe"] = compute_rpe(rir_value, rpe_value)
            processed_set["volume"] = compute_volume(reps_value, weight_value)

            # Check PR
            # We use the set ID we just ensured exists
            set_id = processed_set["id"]
            # We use the exercise index or ID for workout_exercise_id
            workout_exercise_id = str(exercise_index)

            try:
                update_pr_if_needed(
                    user_id=user_id,
                    exercise_id=exercise_id,
                    set_payload=processed_set,
                    workout_id=workout_id,
                    workout_exercise_id=workout_exercise_id,
                    set_id=set_id
                )
            except Exception as e:
                logging.error(f"Failed to update PR for user {user_id}, exercise {exercise_id}: {e}")
                # We continue processing even if PR update fails

            processed_sets.append(processed_set)

        processed_exercise["sets"] = processed_sets
        processed_exercises.append(processed_exercise)

    return processed_exercises
