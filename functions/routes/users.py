from flask import Flask, request, jsonify, g
from config.db import db
from .error_codes import ERROR_CODES
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
import json


def create_users_app():
    # Initialize Flask app
    usersApp = Flask(__name__)

    # Firestore - getUser by ID
    @usersApp.route('/getUser/<id>', methods=['GET'])
    def getUser(id):
        try:
            doc = db.collection('users').document(id).get()
            if not doc.exists:
                return jsonify({
                    "error": ERROR_CODES["USER_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["USER_NOT_FOUND"]["code"],
                    "details": f"User {id} not found"
                }), 404
            user = doc.to_dict()
            user["id"] = id
            friend_ids = user.get("friends", [])
            if not isinstance(friend_ids, list):
                friend_ids = []
            user["friends"] = []
            for friend_id in friend_ids:
                friend_doc = db.collection("users").document(friend_id).get()
                if friend_doc.exists:
                    friend_data = friend_doc.to_dict()
                    user["friends"].append({
                        "id": friend_id,
                        "name": friend_data.get("name", "Unknown")
                    })
            return jsonify(user), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not retrieve user {id}: {e}"
            }), 500

    # Firestore - getUsers
    @usersApp.route('/getUsers', methods=['GET'])
    def getUsers():
        try:
            docData = []
            userCollection = db.collection('users').stream()
            for doc in userCollection:
                # Include the document ID in the response
                user = doc.to_dict()
                user["id"] = doc.id
                # Ensure "friends" field exists as a list
                friend_ids = user.get("friends", [])
                if not isinstance(friend_ids, list):
                    friend_ids = []
                # Populate friends list with names
                user["friends"] = []
                for friend_id in friend_ids:
                    friend_doc = db.collection("users").document(friend_id).get()
                    if friend_doc.exists:
                        friend_data = friend_doc.to_dict()
                        user["friends"].append({
                            "id": friend_id,
                            "name": friend_data.get("name", "Unknown")
                        })
                docData.append(user)
            return jsonify(docData), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not retrieve users: {e}"
            }), 500

    @usersApp.route('/checkUserByPhone', methods=['POST'])
    def checkUserByPhone():
        try:
            data = request.get_json() or {}
            phone = (data.get("phoneNumber") or data.get("phone") or "").strip()
            if not phone:
                return jsonify({
                    "error": ERROR_CODES["INVALID_REQUEST"]["message"],
                    "code": ERROR_CODES["INVALID_REQUEST"]["code"],
                    "details": "phoneNumber is required."
                }), 400

            query = db.collection("users").where("phoneNumber", "==", phone).limit(1)
            user_exists = any(True for _ in query.stream())

            return jsonify({
                "exists": user_exists
            }), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not check phone number: {e}"
            }), 500

    # Firestore - createUser
    @usersApp.route('/createUser', methods=['POST'])
    def createUser():
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                    "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                    "details": "No data provided."
                }), 400
            
            # Add timestamps
            data["createdAt"] = firestore.SERVER_TIMESTAMP
            data["updatedAt"] = firestore.SERVER_TIMESTAMP

            # sanitize firstName and lastName
            first_name = data.get("firstName", "")
            last_name = data.get("lastName", "")
            if first_name:
                first_name.capitalize()
                data["firstName"] = first_name
            if last_name:
                last_name.capitalize()
                data["lastName"] = last_name
            
            #additional user data not asked during onboarding
            data["affiliations"] = data.get("affiliations", "")
            data["bio"] = data.get("bio", "")
            data["favoritePlaces"] = data.get("favoritePlaces", [])
            data["playFrequency"] = data.get("playFrequency", "Monthly")
            data["preferredEventTypes"] = data.get("preferredEventTypes", [])
            data["imageUrl"] = data.get("imageUrl", "")
            if data.get("gender") is None:
                data["gender"] = "N/A"


            uid = data["id"]
            db.collection('users').document(uid).create(data)

            return jsonify({
                "message": "User created",
                "uid": uid
            }), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["USER_CREATION_FAILED"]["message"],
                "code": ERROR_CODES["USER_CREATION_FAILED"]["code"],
                "details": f"Could not create user: {e}"
            }), 500

    # Firestore - deleteUser by ID
    @usersApp.route('/deleteUser/<id>', methods=['DELETE'])
    def deleteUser(id):
        try:
            doc = db.collection('users').document(id).get()
            if doc.exists:
                db.collection('users').document(id).delete() # for some reason it won't work with doc.delete()
                return jsonify({"message": f"User {id} deleted"}), 200
            else:
                return jsonify({
                    "error": ERROR_CODES["USER_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["USER_NOT_FOUND"]["code"],
                    "details": f"User {id} not found"
                }), 404
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["USER_DELETE_FAILED"]["message"],
                "code": ERROR_CODES["USER_DELETE_FAILED"]["code"],
                "details": f"Could not delete user {id}: {e}"
            }), 500

    # Firestore - updateUser by ID
    @usersApp.route('/updateUser/<id>', methods=['PUT'])
    def updateUser(id):
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "error": ERROR_CODES["NO_DATA_PROVIDED"]["message"],
                    "code": ERROR_CODES["NO_DATA_PROVIDED"]["code"],
                    "details": "No data provided."
                }), 400
            doc = db.collection('users').document(id).get()
            if doc.exists:
                # Add updatedAt timestamp
                data["updatedAt"] = firestore.SERVER_TIMESTAMP

                first_name = data.get("firstName", "")
                last_name = data.get("lastName", "")
                if first_name:
                    first_name.capitalize()
                    data["firstName"] = first_name
                if last_name:
                    last_name.capitalize()
                    data["lastName"] = last_name

                db.collection('users').document(id).update(data)
                return jsonify({"message": f"User {id} updated"}), 200
            else:
                return jsonify({
                    "error": ERROR_CODES["USER_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["USER_NOT_FOUND"]["code"],
                    "details": f"User {id} not found"
                }), 404
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["USER_UPDATE_FAILED"]["message"],
                "code": ERROR_CODES["USER_UPDATE_FAILED"]["code"],
                "details": f"Could not update user {id}: {e}"
            }), 500
        
    # Firestore - getUser by ID
    @usersApp.route('/getUserV2/<id>', methods=['GET'])
    def getUserV2(id):
        try:
            doc = db.collection('users').document(id).get()
            if not doc.exists:
                return jsonify({
                    "error": ERROR_CODES["USER_NOT_FOUND"]["message"],
                    "code": ERROR_CODES["USER_NOT_FOUND"]["code"],
                    "details": f"User {id} not found"
                }), 404
            user = doc.to_dict()
            user["id"] = id

            viewer_id = request.args.get("viewerId")
            if not viewer_id:
                viewer_id = getattr(g, "user", {}).get("uid") if hasattr(g, "user") else None

            following_set = set()
            if viewer_id:
                viewer_doc = db.collection("users").document(viewer_id).get()
                if viewer_doc.exists:
                    viewer_data = viewer_doc.to_dict() or {}
                    following_list = viewer_data.get("following", [])
                    if isinstance(following_list, list):
                        following_set = {str(fid) for fid in following_list if fid}

            friend_ids = user.get("friends", [])
            if not isinstance(friend_ids, list):
                friend_ids = []
            user["friends"] = []
            for friend_id in friend_ids:
                friend_doc = db.collection("users").document(friend_id).get()
                if friend_doc.exists:
                    friend_data = friend_doc.to_dict()
                    user["friends"].append({
                        "id": friend_id,
                        "name": friend_data.get("name", "Unknown")
                    })

            return jsonify(user), 200
        except Exception as e:
            return jsonify({
                "error": ERROR_CODES["INTERNAL_SERVER_ERROR"]["message"],
                "code": ERROR_CODES["INTERNAL_SERVER_ERROR"]["code"],
                "details": f"Could not retrieve user {id}: {e}"
            }), 500
        
    return usersApp
