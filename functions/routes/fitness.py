from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Flask, Response, g, jsonify, request

from config.db import db
from helpers.auth_helpers import AuthError, verify_authorization_header
from helpers.fitness_helpers import (
    build_analytics_payload,
    build_day_payload,
    build_exercise_history_payload,
    build_last_sessions_payload,
    build_previous_workout_payload,
    build_records_payload,
    build_workout_calendar_payload,
    copy_exercises_from_date_payload,
    create_fitness_exercise,
    delete_fitness_exercise,
    list_exercise_options,
    reorder_fitness_exercises,
    update_fitness_exercise,
)
from helpers.fitness_profile_helpers import (
    build_fitness_profile_payload,
    build_weight_history_payload,
    create_weight_entry_payload,
    delete_weight_entry_payload,
    save_fitness_profile_payload,
    update_weight_entry_payload,
)


def _ok(payload: dict[str, Any] | None = None, status: int = 200):
    return jsonify({"status": "ok", "error": None, **(payload or {})}), status


def _error(message: str, status: int):
    return jsonify({"status": "error", "error": message}), status


def _query_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _read_json_body() -> dict[str, Any]:
    if not request.data:
        return {}
    data = request.get_json(silent=True)
    if data is None:
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object.")
    return data


def _handle(handler: Callable[[], dict[str, Any]]):
    try:
        return _ok(handler())
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("Unable to resolve") or message.startswith("Firestore is not configured"):
            return _error(message, 503)
        logging.exception("FitTrack API runtime failure")
        return _error("Unable to process FitTrack request right now.", 500)
    except Exception:
        logging.exception("FitTrack API request failed")
        return _error("Unable to process FitTrack request right now.", 500)


def create_fitness_app():
    fitness_app = Flask(__name__)
    fitness_app.url_map.strict_slashes = False

    @fitness_app.before_request
    def attach_firebase_user():
        if request.method == "OPTIONS":
            return Response(status=204)
        try:
            g.auth_user = verify_authorization_header(request.headers.get("Authorization"))
        except AuthError as exc:
            return _error(str(exc), 401)
        return None

    @fitness_app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    def fit_route(rule: str, *, methods: list[str]):
        def decorator(fn):
            fitness_app.add_url_rule(rule, endpoint=fn.__name__, view_func=fn, methods=methods)
            fitness_app.add_url_rule(
                f"/api/fitness{rule}",
                endpoint=f"api_{fn.__name__}",
                view_func=fn,
                methods=methods,
            )
            return fn
        return decorator

    @fit_route("/day/", methods=["GET"])
    def fitness_day_api():
        return _handle(
            lambda: build_day_payload(
                db,
                auth_user=g.auth_user,
                workout_date=request.args.get("date"),
            )
        )

    @fit_route("/exercise-options/", methods=["GET"])
    def fitness_exercise_options_api():
        return _handle(lambda: list_exercise_options(db, auth_user=g.auth_user))

    @fit_route("/analytics/", methods=["GET"])
    def fitness_analytics_api():
        return _handle(
            lambda: build_analytics_payload(
                db,
                auth_user=g.auth_user,
                range_key=request.args.get("range"),
                start_date=request.args.get("start_date"),
                end_date=request.args.get("end_date"),
                muscle_split_metric=request.args.get("split_metric"),
                volume_category=request.args.get("volume_category"),
            )
        )

    @fit_route("/records/", methods=["GET"])
    def fitness_records_api():
        return _handle(
            lambda: build_records_payload(
                db,
                auth_user=g.auth_user,
                query=request.args.get("q"),
                sort_key=request.args.get("sort"),
                page=_query_int("page", default=1, minimum=1, maximum=1000),
                page_size=_query_int("page_size", default=24, minimum=1, maximum=100),
                range_key=request.args.get("range"),
                start_date=request.args.get("start_date"),
                end_date=request.args.get("end_date"),
            )
        )

    @fit_route("/profile/", methods=["GET", "POST"])
    def fitness_profile_api():
        if request.method == "GET":
            return _handle(lambda: build_fitness_profile_payload(db, auth_user=g.auth_user))
        return _handle(
            lambda: save_fitness_profile_payload(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
            )
        )

    @fit_route("/profile/weight-history/", methods=["GET"])
    def fitness_weight_history_api():
        return _handle(
            lambda: build_weight_history_payload(
                db,
                auth_user=g.auth_user,
                range_key=request.args.get("range"),
                start_date=request.args.get("start_date"),
                end_date=request.args.get("end_date"),
            )
        )

    @fit_route("/profile/weight-history/create/", methods=["POST"])
    def fitness_create_weight_entry_api():
        return _handle(
            lambda: create_weight_entry_payload(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
            )
        )

    @fit_route("/profile/weight-history/<string:entry_id>/update/", methods=["POST"])
    def fitness_update_weight_entry_api(entry_id: str):
        return _handle(
            lambda: update_weight_entry_payload(
                db,
                auth_user=g.auth_user,
                entry_id=entry_id,
                payload=_read_json_body(),
            )
        )

    @fit_route("/profile/weight-history/<string:entry_id>/delete/", methods=["POST"])
    def fitness_delete_weight_entry_api(entry_id: str):
        return _handle(
            lambda: delete_weight_entry_payload(
                db,
                auth_user=g.auth_user,
                entry_id=entry_id,
            )
        )

    @fit_route("/exercises/create/", methods=["POST"])
    def fitness_create_exercise_api():
        return _handle(
            lambda: create_fitness_exercise(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
            )
        )

    @fit_route("/exercises/<string:exercise_id>/update/", methods=["POST"])
    def fitness_update_exercise_api(exercise_id: str):
        return _handle(
            lambda: update_fitness_exercise(
                db,
                auth_user=g.auth_user,
                exercise_id=exercise_id,
                payload=_read_json_body(),
            )
        )

    @fit_route("/exercises/<string:exercise_id>/delete/", methods=["POST"])
    def fitness_delete_exercise_api(exercise_id: str):
        return _handle(
            lambda: delete_fitness_exercise(
                db,
                auth_user=g.auth_user,
                exercise_id=exercise_id,
            )
        )

    @fit_route("/exercises/reorder/", methods=["POST"])
    def fitness_reorder_exercises_api():
        return _handle(
            lambda: reorder_fitness_exercises(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
            )
        )

    @fit_route("/exercises/last-sessions/", methods=["GET"])
    def fitness_last_sessions_api():
        return _handle(
            lambda: build_last_sessions_payload(
                db,
                auth_user=g.auth_user,
                date_iso=request.args.get("date"),
            )
        )

    @fit_route("/exercises/previous-workout/", methods=["GET"])
    def fitness_previous_workout_api():
        return _handle(
            lambda: build_previous_workout_payload(
                db,
                auth_user=g.auth_user,
                before_date=request.args.get("before"),
            )
        )

    @fit_route("/exercises/copy-from-date/", methods=["POST"])
    def fitness_copy_exercises_api():
        return _handle(
            lambda: copy_exercises_from_date_payload(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
            )
        )

    @fit_route("/exercise-history/", methods=["GET"])
    def fitness_exercise_history_api():
        return _handle(
            lambda: build_exercise_history_payload(
                db,
                auth_user=g.auth_user,
                exercise_name=request.args.get("name", ""),
            )
        )

    @fit_route("/workout-calendar/", methods=["GET"])
    def fitness_workout_calendar_api():
        return _handle(
            lambda: build_workout_calendar_payload(
                db,
                auth_user=g.auth_user,
                range_key=request.args.get("range"),
                start_date=request.args.get("start_date"),
                end_date=request.args.get("end_date"),
            )
        )

    return fitness_app
