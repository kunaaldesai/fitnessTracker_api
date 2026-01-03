from flask import Flask, request, jsonify
from config.db import db
from .error_codes import ERROR_CODES
from firebase_admin import firestore
from datetime import datetime
from helpers.workouts_helpers import (
    parse_bool,
    compute_rpe,
    get_workout_ref,
    get_item_ref,
    attach_sets,
    update_pr_if_needed,
)


def create_workouts_app():
    workoutsApp = Flask(__name__)

    # Exercises
    @workoutsApp.route('/users/<user_id>/exercises', methods=['POST', 'GET'])
    def exercises(user_id):
        try:
            if request.method == 'POST':
                data = request.get_json() or {}
                name = str(data.get("name", "")).strip()
                if not name:
                    return jsonify({
                        "error": ERROR_CODES["INVALID_REQUEST"]["message"],
                        "code": ERROR_CODES["INVALID_REQUEST"]["code"],
                        "details": "name is required"
                    }), 400

                exercise_ref = db.collection("users").document(user_id).collection("exercises").document()
                exercise_data = {
                    "name": name,
                    "muscleGroups": data.get("muscleGroups", []),
                    "equipment": data.get("equipment", ""),
                    "notes": data.get("notes", ""),
                    "archived": parse_bool(data.get("archived"), False),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP
                }
                exercise_ref.set(exercise_data)
                return jsonify({
                    "message": "Exercise created",
                    "id": exercise_ref.id
                }), 200

            include_archived = parse_bool(request.args.get("includeArchived"), False)
            exercise_query = db.collection("users").document(user_id).collection("exercises")
            if not include_archived:
                exercise_query = exercise_query.where("archived", "==", False)

            exercises = []
            for doc in exercise_query.stream():
                exercise = doc.to_dict()
                exercise["id"] = doc.id
                exercises.append(exercise)
            return jsonify(exercises), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not handle exercises for user {user_id}: {e}"
            }), 500

    @workoutsApp.route('/users/<user_id>/exercises/<exercise_id>', methods=['GET', 'PUT', 'DELETE'])
    def exercise_detail(user_id, exercise_id):
        try:
            exercise_ref = db.collection("users").document(user_id).collection("exercises").document(exercise_id)
            exercise_doc = exercise_ref.get()
            if not exercise_doc.exists:
                return jsonify({
                    "error": ERROR_CODES["EXERCISE_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["EXERCISE_NOT_FOUND"]["code"],
                    "details": f"Exercise {exercise_id} not found for user {user_id}"
                }), 404

            if request.method == 'GET':
                exercise = exercise_doc.to_dict()
                exercise["id"] = exercise_doc.id
                return jsonify(exercise), 200

            if request.method == 'PUT':
                data = request.get_json() or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400
                data["updatedAt"] = firestore.SERVER_TIMESTAMP
                exercise_ref.update(data)
                return jsonify({"message": f"Exercise {exercise_id} updated"}), 200

            exercise_ref.delete()
            return jsonify({"message": f"Exercise {exercise_id} deleted"}), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process exercise {exercise_id} for user {user_id}: {e}"
            }), 500

    # Workouts
    @workoutsApp.route('/users/<user_id>/workouts', methods=['POST', 'GET'])
    def workouts(user_id):
        try:
            if request.method == 'POST':
                data = request.get_json() or {}
                date_value = data.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
                workout_ref = db.collection("users").document(user_id).collection("workouts").document()
                workout_data = {
                    "date": date_value,
                    "startTime": data.get("startTime"),
                    "endTime": data.get("endTime"),
                    "notes": data.get("notes", ""),
                    "timezone": data.get("timezone"),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP
                }
                workout_ref.set(workout_data)
                return jsonify({
                    "message": "Workout created",
                    "id": workout_ref.id
                }), 200

            start_date = request.args.get("startDate")
            end_date = request.args.get("endDate")
            limit = request.args.get("limit")

            workout_query = db.collection("users").document(user_id).collection("workouts")
            if start_date:
                workout_query = workout_query.where("date", ">=", start_date)
            if end_date:
                workout_query = workout_query.where("date", "<=", end_date)
            workout_query = workout_query.order_by("date", direction=firestore.Query.DESCENDING)
            if limit:
                try:
                    workout_query = workout_query.limit(int(limit))
                except (TypeError, ValueError):
                    pass

            workouts_list = []
            for doc in workout_query.stream():
                workout = doc.to_dict()
                workout["id"] = doc.id
                workouts_list.append(workout)
            return jsonify(workouts_list), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workouts for user {user_id}: {e}"
            }), 500

    @workoutsApp.route('/users/<user_id>/workouts/<workout_id>', methods=['GET', 'PUT', 'DELETE'])
    def workout_detail(user_id, workout_id):
        try:
            workout_ref, workout_doc = get_workout_ref(user_id, workout_id)
            if workout_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {workout_id} not found for user {user_id}"
                }), 404

            if request.method == 'GET':
                workout = workout_doc.to_dict()
                workout["id"] = workout_doc.id
                include_items = parse_bool(request.args.get("includeItems"), False)
                include_sets = parse_bool(request.args.get("includeSets"), True)
                if include_items:
                    items_ref = workout_ref.collection("items")
                    items = []
                    for item_doc in items_ref.order_by("order").stream():
                        item = item_doc.to_dict()
                        item["id"] = item_doc.id
                        item["sets"] = attach_sets(item_doc.reference, include_sets)
                        items.append(item)
                    workout["items"] = items
                return jsonify(workout), 200

            if request.method == 'PUT':
                data = request.get_json() or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400
                data["updatedAt"] = firestore.SERVER_TIMESTAMP
                workout_ref.update(data)
                return jsonify({"message": f"Workout {workout_id} updated"}), 200

            try:
                items_ref = workout_ref.collection("items")
                for item_doc in items_ref.stream():
                    sets_ref = item_doc.reference.collection("sets")
                    for set_doc in sets_ref.stream():
                        set_doc.reference.delete()
                    item_doc.reference.delete()
                workout_ref.delete()
            except Exception as deletion_error:
                return jsonify({
                    "error": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["message"],
                    "code": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["code"],
                    "details": f"Could not delete workout {workout_id}: {deletion_error}"
                }), 500

            return jsonify({"message": f"Workout {workout_id} deleted"}), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout {workout_id} for user {user_id}: {e}"
            }), 500

    # Workout exercises
    @workoutsApp.route('/users/<user_id>/workouts/<workout_id>/items', methods=['POST', 'GET'])
    def workout_items(user_id, workout_id):
        try:
            workout_ref, workout_doc = get_workout_ref(user_id, workout_id)
            if workout_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {workout_id} not found for user {user_id}"
                }), 404

            if request.method == 'POST':
                data = request.get_json() or {}
                exercise_id = data.get("exerciseId")
                if not exercise_id:
                    return jsonify({
                        "error": ERROR_CODES["INVALID_REQUEST"]["message"],
                        "code": ERROR_CODES["INVALID_REQUEST"]["code"],
                        "details": "exerciseId is required"
                    }), 400

                exercise_doc = db.collection("users").document(user_id).collection("exercises").document(exercise_id).get()
                if not exercise_doc.exists:
                    return jsonify({
                        "error": ERROR_CODES["EXERCISE_NOT_FOUND"]["message"],
                        "code": ERROR_CODES["EXERCISE_NOT_FOUND"]["code"],
                        "details": f"Exercise {exercise_id} not found for user {user_id}"
                    }), 404

                item_ref = workout_ref.collection("items").document()
                item_data = {
                    "exerciseId": exercise_id,
                    "name": data.get("name") or exercise_doc.to_dict().get("name"),
                    "notes": data.get("notes", ""),
                    "order": data.get("order", 0),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP
                }
                item_ref.set(item_data)
                return jsonify({
                    "message": "Workout exercise added",
                    "id": item_ref.id
                }), 200

            include_sets = parse_bool(request.args.get("includeSets"), False)
            items_ref = workout_ref.collection("items").order_by("order")
            items = []
            for item_doc in items_ref.stream():
                item = item_doc.to_dict()
                item["id"] = item_doc.id
                item["sets"] = attach_sets(item_doc.reference, include_sets)
                items.append(item)
            return jsonify(items), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout exercises for workout {workout_id}: {e}"
            }), 500

    @workoutsApp.route('/users/<user_id>/workouts/<workout_id>/items/<item_id>', methods=['GET', 'PUT', 'DELETE'])
    def workout_item_detail(user_id, workout_id, item_id):
        try:
            workout_ref, item_ref, item_doc = get_item_ref(user_id, workout_id, item_id)
            if workout_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {workout_id} not found for user {user_id}"
                }), 404
            if item_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["code"],
                    "details": f"Workout exercise {item_id} not found in workout {workout_id}"
                }), 404

            if request.method == 'GET':
                include_sets = parse_bool(request.args.get("includeSets"), True)
                item = item_doc.to_dict()
                item["id"] = item_doc.id
                item["sets"] = attach_sets(item_ref, include_sets)
                return jsonify(item), 200

            if request.method == 'PUT':
                data = request.get_json() or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400
                data["updatedAt"] = firestore.SERVER_TIMESTAMP
                item_ref.update(data)
                return jsonify({"message": f"Workout exercise {item_id} updated"}), 200

            try:
                sets_ref = item_ref.collection("sets")
                for set_doc in sets_ref.stream():
                    set_doc.reference.delete()
                item_ref.delete()
            except Exception as deletion_error:
                return jsonify({
                    "error": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["message"],
                    "code": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["code"],
                    "details": f"Could not delete workout exercise {item_id}: {deletion_error}"
                }), 500

            return jsonify({"message": f"Workout exercise {item_id} deleted"}), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout exercise {item_id}: {e}"
            }), 500

    # Sets
    @workoutsApp.route('/users/<user_id>/workouts/<workout_id>/items/<item_id>/sets', methods=['POST', 'GET'])
    def workout_sets(user_id, workout_id, item_id):
        try:
            workout_ref, item_ref, item_doc = get_item_ref(user_id, workout_id, item_id)
            if workout_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {workout_id} not found for user {user_id}"
                }), 404
            if item_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["code"],
                    "details": f"Workout exercise {item_id} not found in workout {workout_id}"
                }), 404

            if request.method == 'POST':
                data = request.get_json() or {}
                if data.get("reps") is None:
                    return jsonify({
                        "error": ERROR_CODES["INVALID_REQUEST"]["message"],
                        "code": ERROR_CODES["INVALID_REQUEST"]["code"],
                        "details": "reps is required"
                    }), 400

                rir_value = data.get("rir")
                rpe_value = data.get("rpe")
                set_payload = {
                    "reps": data.get("reps"),
                    "weight": data.get("weight", 0),
                    "rir": rir_value,
                    "rpe": compute_rpe(rir_value, rpe_value),
                    "isPR": parse_bool(data.get("isPR"), False),
                    "notes": data.get("notes", ""),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP
                }

                set_ref = item_ref.collection("sets").document()
                set_ref.set(set_payload)

                try:
                    update_pr_if_needed(user_id, item_doc.to_dict().get("exerciseId"), set_payload, workout_id, item_id, set_ref.id)
                except Exception as pr_error:
                    return jsonify({
                        "error": ERROR_CODES["PR_UPDATE_FAILED"]["message"],
                        "code": ERROR_CODES["PR_UPDATE_FAILED"]["code"],
                        "details": f"Set saved but PR update failed: {pr_error}"
                    }), 500

                item_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})
                workout_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})

                return jsonify({
                    "message": "Set added",
                    "id": set_ref.id
                }), 200

            sets_ref = item_ref.collection("sets").order_by("createdAt")
            sets = []
            for set_doc in sets_ref.stream():
                set_data = set_doc.to_dict()
                set_data["id"] = set_doc.id
                sets.append(set_data)
            return jsonify(sets), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process sets for workout exercise {item_id}: {e}"
            }), 500

    @workoutsApp.route('/users/<user_id>/workouts/<workout_id>/items/<item_id>/sets/<set_id>', methods=['PUT', 'DELETE'])
    def workout_set_detail(user_id, workout_id, item_id, set_id):
        try:
            workout_ref, item_ref, item_doc = get_item_ref(user_id, workout_id, item_id)
            if workout_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {workout_id} not found for user {user_id}"
                }), 404
            if item_ref is None:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_ITEM_NOT_FOUND"]["code"],
                    "details": f"Workout exercise {item_id} not found in workout {workout_id}"
                }), 404

            set_ref = item_ref.collection("sets").document(set_id)
            set_doc = set_ref.get()
            if not set_doc.exists:
                return jsonify({
                    "error": ERROR_CODES["SET_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["SET_NOT_FOUND"]["code"],
                    "details": f"Set {set_id} not found in workout exercise {item_id}"
                }), 404

            if request.method == 'PUT':
                data = request.get_json() or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400

                if "rpe" not in data and "rir" in data:
                    data["rpe"] = compute_rpe(data.get("rir"), None)

                data["updatedAt"] = firestore.SERVER_TIMESTAMP
                set_ref.update(data)
                item_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})
                workout_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})
                return jsonify({"message": f"Set {set_id} updated"}), 200

            set_ref.delete()
            item_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})
            workout_ref.update({"updatedAt": firestore.SERVER_TIMESTAMP})
            return jsonify({"message": f"Set {set_id} deleted"}), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process set {set_id} for workout exercise {item_id}: {e}"
            }), 500

    return workoutsApp
