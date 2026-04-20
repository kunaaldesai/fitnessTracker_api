from flask import Flask, request, jsonify
import concurrent.futures
from config.db import db
from .error_codes import ERROR_CODES
from firebase_admin import firestore
from datetime import datetime
import logging
from helpers.workouts_helpers import (
    parse_bool,
    compute_rpe,
    compute_volume,
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
                data = request.get_json(silent=True) or {}
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
            logging.error(f"Could not handle exercises for user {user_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not handle exercises for user {user_id}"
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
                data = request.get_json(silent=True) or {}
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
            logging.error(f"Could not process exercise {exercise_id} for user {user_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process exercise {exercise_id} for user {user_id}"
            }), 500

    # Workouts
    @workoutsApp.route('/users/<user_id>/workouts', methods=['POST', 'GET'])
    def workouts(user_id):
        try:
            if request.method == 'POST':
                data = request.get_json(silent=True) or {}
                date_value = data.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
                workout_ref = db.collection("users").document(user_id).collection("workouts").document()
                workout_data = {
                    "date": date_value, # get from user device, not an input
                    "notes": data.get("notes", ""), # optional user input
                    "timezone": data.get("timezone"), # get from user device, not an input
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                    # now the actual inputs
                    "workout_id": data.get("workout_id") # the workout from the workouts collection in the db
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
            logging.error(f"Could not process workouts for user {user_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workouts for user {user_id}"
            }), 500

    @workoutsApp.route('/users/<user_id>/workouts/start', methods=['POST'])
    def start_workout(user_id):
        try:
            data = request.get_json(silent=True) or {}
            template_id = data.get("workout_id")
            if not template_id:
                return jsonify({
                    "error": ERROR_CODES["INVALID_REQUEST"]["message"],
                    "code": ERROR_CODES["INVALID_REQUEST"]["code"],
                    "details": "workout_id is required"
                }), 400

            template_ref = db.collection("workouts").document(template_id)
            template_doc = template_ref.get()
            if not template_doc.exists:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {template_id} not found"
                }), 404

            date_value = data.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
            workout_ref = db.collection("users").document(user_id).collection("workouts").document()
            workout_data = {
                "date": date_value,
                "notes": data.get("notes", ""),
                "timezone": data.get("timezone"),
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "workout_id": template_id
            }

            template_data = template_doc.to_dict() or {}
            exercises = template_data.get("exercises") or []
            if not isinstance(exercises, list):
                exercises = []

            batch = db.batch()
            batch.set(workout_ref, workout_data)

            # BOLT: Optimize N+1 query problem by pre-fetching missing exercise names
            missing_name_refs = {}
            for exercise in exercises:
                exercise_id = None
                name = None
                if isinstance(exercise, dict):
                    exercise_id = exercise.get("exerciseId") or exercise.get("exercise_id") or exercise.get("id")
                    name = exercise.get("name") or exercise.get("exerciseName") or exercise.get("title")
                else:
                    if exercise is not None:
                        name = str(exercise)

                if exercise_id is not None and not isinstance(exercise_id, str):
                    exercise_id = str(exercise_id)
                if name is not None and not isinstance(name, str):
                    name = str(name)

                if not name and exercise_id:
                    missing_name_refs[exercise_id] = db.collection("users").document(user_id).collection("exercises").document(exercise_id)

            exercise_lookup = {}
            if missing_name_refs:
                docs = db.get_all(list(missing_name_refs.values()))
                for doc in docs:
                    if doc.exists:
                        exercise_lookup[doc.id] = doc.to_dict().get("name")

            for index, exercise in enumerate(exercises):
                exercise_id = None
                name = None
                notes = ""
                order = index

                if isinstance(exercise, dict):
                    exercise_id = exercise.get("exerciseId") or exercise.get("exercise_id") or exercise.get("id")
                    name = exercise.get("name") or exercise.get("exerciseName") or exercise.get("title")
                    notes = exercise.get("notes", "")
                    order_value = exercise.get("order")
                    if order_value is not None:
                        try:
                            order = int(order_value)
                        except (TypeError, ValueError):
                            order = index
                else:
                    if exercise is not None:
                        name = str(exercise)

                if exercise_id is not None and not isinstance(exercise_id, str):
                    exercise_id = str(exercise_id)
                if name is not None and not isinstance(name, str):
                    name = str(name)

                if not name and exercise_id:
                    name = exercise_lookup.get(exercise_id)

                if not name and not exercise_id:
                    continue

                item_ref = workout_ref.collection("items").document()
                item_data = {
                    "notes": notes,
                    "order": order,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP
                }
                if exercise_id:
                    item_data["exerciseId"] = exercise_id
                if name:
                    item_data["name"] = name

                batch.set(item_ref, item_data)

            batch.commit()

            return jsonify({
                "message": "Workout started",
                "id": workout_ref.id
            }), 200
        except Exception as e:
            logging.error(f"Could not start workout for user {user_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not start workout for user {user_id}"
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
                    item_docs = list(items_ref.order_by("order").stream())

                    def process_item(item_doc):
                        item = item_doc.to_dict()
                        item["id"] = item_doc.id
                        item["sets"] = attach_sets(item_doc.reference, include_sets)
                        return item

                    # BOLT: Optimize N+1 query problem by fetching sets in parallel
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        items = list(executor.map(process_item, item_docs))

                    workout["items"] = items
                return jsonify(workout), 200

            if request.method == 'PUT':
                data = request.get_json(silent=True) or {}
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
                logging.error(f"Could not delete workout {workout_id}: {deletion_error}")
                return jsonify({
                    "error": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["message"],
                    "code": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["code"],
                    "details": f"Could not delete workout {workout_id}"
                }), 500

            return jsonify({"message": f"Workout {workout_id} deleted"}), 200
        except Exception as e:
            logging.error(f"Could not process workout {workout_id} for user {user_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout {workout_id} for user {user_id}"
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
                data = request.get_json(silent=True) or {}
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

            item_docs = list(items_ref.stream())

            def process_item(item_doc):
                item = item_doc.to_dict()
                item["id"] = item_doc.id
                item["sets"] = attach_sets(item_doc.reference, include_sets)
                return item

            # BOLT: Optimize N+1 query problem by fetching sets in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                items = list(executor.map(process_item, item_docs))

            return jsonify(items), 200
        except Exception as e:
            logging.error(f"Could not process workout exercises for workout {workout_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout exercises for workout {workout_id}"
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
                data = request.get_json(silent=True) or {}
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
                logging.error(f"Could not delete workout exercise {item_id}: {deletion_error}")
                return jsonify({
                    "error": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["message"],
                    "code": ERROR_CODES["FIRESTORE_DELETE_FAILED"]["code"],
                    "details": f"Could not delete workout exercise {item_id}"
                }), 500

            return jsonify({"message": f"Workout exercise {item_id} deleted"}), 200
        except Exception as e:
            logging.error(f"Could not process workout exercise {item_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process workout exercise {item_id}"
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
                data = request.get_json(silent=True) or {}
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
                    "volume": compute_volume(data.get("reps"), data.get("weight", 0)),
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
                    logging.error(f"Set saved but PR update failed: {pr_error}")
                    return jsonify({
                        "error": ERROR_CODES["PR_UPDATE_FAILED"]["message"],
                        "code": ERROR_CODES["PR_UPDATE_FAILED"]["code"],
                        "details": "Set saved but PR update failed"
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
            logging.error(f"Could not process sets for workout exercise {item_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process sets for workout exercise {item_id}"
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
                data = request.get_json(silent=True) or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400

                if "rpe" not in data and "rir" in data:
                    data["rpe"] = compute_rpe(data.get("rir"), None)

                if "reps" in data or "weight" in data:
                    current_data = set_doc.to_dict()
                    reps_value = data.get("reps", current_data.get("reps"))
                    weight_value = data.get("weight", current_data.get("weight"))
                    data["volume"] = compute_volume(reps_value, weight_value)

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
            logging.error(f"Could not process set {set_id} for workout exercise {item_id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not process set {set_id} for workout exercise {item_id}"
            }), 500
        
    # Firestore - getWorkout by ID
    @workoutsApp.route('/getWorkout/<id>', methods=['GET'])
    def getWorkout(id):
        try:
            doc = db.collection('workouts').document(id).get()
            if not doc.exists:
                return jsonify({
                    "error": ERROR_CODES["WORKOUT_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["WORKOUT_NOT_FOUND"]["code"],
                    "details": f"Workout {id} not found"
                }), 404
            workout = doc.to_dict()
            workout["id"] = id
            return jsonify(workout), 200
        except Exception as e:
            logging.error(f"Could not retrieve workout {id}: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not retrieve workout {id}"
            }), 500
        
    # get all workouts
    @workoutsApp.route('/getAllWorkouts', methods=['GET'])
    def getAllWorkouts():
        try:
            workouts = []
            docs = db.collection('workouts').stream()
            for doc in docs:
                workout = doc.to_dict()
                workout["id"] = doc.id
                workouts.append(workout)
            return jsonify(workouts), 200
        except Exception as e:
            logging.error(f"Could not retrieve workouts: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": "Could not retrieve workouts"
            }), 500
        
    # create workouts
    @workoutsApp.route('/createWorkout', methods=['POST'])
    def createWorkout(): # fields: description, default, exercises, muscle_group, name, number_of_exercises, sets, type
        try:
            data = request.get_json(silent=True) or {}
            workout_ref = db.collection("workouts").document()
            workout_data = {
                "description": data.get("description", ""),
                "default": data.get("default", False), # dont allow user input
                "exercises": data.get("exercises", []),
                "equipment": data.get("equipment", []),
                "muscle_group": data.get("muscle_group", []),
                "name": data.get("name", ""),
                "number_of_exercises": data.get("number_of_exercises", 0),
                "sets": data.get("sets", 0),
                "type": data.get("type", ""),
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP
            }
            workout_ref.set(workout_data)
            return jsonify({
                "message": "Workout created",
                "id": workout_ref.id
            }), 200
        except Exception as e:
            logging.error(f"Could not create workout: {e}")
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": "Could not create workout"
            }), 500

    return workoutsApp
