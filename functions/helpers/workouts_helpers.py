from config.db import db
from firebase_admin import firestore


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


def get_workout_ref(user_id, workout_id):
    workout_ref = db.collection("users").document(user_id).collection("workouts").document(workout_id)
    workout_doc = workout_ref.get()
    if not workout_doc.exists:
        return None, None
    return workout_ref, workout_doc


def get_item_ref(user_id, workout_id, item_id):
    workout_ref, workout_doc = get_workout_ref(user_id, workout_id)
    if workout_ref is None:
        return None, None, None
    item_ref = workout_ref.collection("items").document(item_id)
    item_doc = item_ref.get()
    if not item_doc.exists:
        return workout_ref, None, None
    return workout_ref, item_ref, item_doc


def attach_sets(item_ref, include_sets):
    if not include_sets:
        return []
    sets_ref = item_ref.collection("sets")
    sets = []
    for set_doc in sets_ref.order_by("createdAt").stream():
        set_data = set_doc.to_dict()
        set_data["id"] = set_doc.id
        sets.append(set_data)
    return sets


def update_pr_if_needed(user_id, exercise_id, set_payload, workout_id, workout_exercise_id, set_id):
    try:
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
