from flask import Flask, request, jsonify
import concurrent.futures
from config.db import db
from .error_codes import ERROR_CODES
from firebase_admin import firestore
from datetime import datetime, timezone
import logging
from helpers.workouts_helpers import (
    parse_bool,
    get_workout_ref,
    process_workout_exercises,
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
                date_value = data.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                workout_ref = db.collection("users").document(user_id).collection("workouts").document()

                # Check for nested exercises
                exercises_data = data.get("exercises", [])

                # Process exercises using helper
                processed_exercises = process_workout_exercises(user_id, workout_ref.id, exercises_data)

                workout_data = {
                    "date": date_value, # get from user device, not an input
                    "notes": data.get("notes", ""), # optional user input
                    "timezone": data.get("timezone"), # get from user device, not an input
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                    # now the actual inputs
                    "workout_id": data.get("workout_id"), # the workout from the workouts collection in the db
                    "exercises": processed_exercises
                }
                workout_ref.set(workout_data)
                return jsonify({
                    "message": "Workout saved",
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
                return jsonify(workout), 200

            if request.method == 'PUT':
                data = request.get_json(silent=True) or {}
                if not data:
                    return jsonify({
                        "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                        "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                        "details": "No update data provided."
                    }), 400

                if "exercises" in data:
                    exercises_data = data["exercises"]
                    processed_exercises = process_workout_exercises(user_id, workout_id, exercises_data)
                    data["exercises"] = processed_exercises

                data["updatedAt"] = firestore.SERVER_TIMESTAMP
                workout_ref.update(data)
                return jsonify({"message": f"Workout {workout_id} updated"}), 200

            try:
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
