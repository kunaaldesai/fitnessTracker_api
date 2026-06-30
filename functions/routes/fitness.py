from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
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
    delete_account_payload,
    delete_weight_entry_payload,
    save_fitness_profile_payload,
    update_weight_entry_payload,
)


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    "ip": RateLimitRule(limit=600, window_seconds=60),
    "user": RateLimitRule(limit=300, window_seconds=60),
    "user_write": RateLimitRule(limit=180, window_seconds=60),
}
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = Lock()
_MAX_RATE_LIMIT_BUCKETS = 10000


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


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.remote_addr or "unknown"


def _rate_limit_check(bucket_key: str, rule: RateLimitRule, *, now: float | None = None) -> tuple[bool, int]:
    current_time = time.monotonic() if now is None else now
    cutoff = current_time - rule.window_seconds
    with _RATE_LIMIT_LOCK:
        if len(_RATE_LIMIT_BUCKETS) > _MAX_RATE_LIMIT_BUCKETS:
            stale_keys = [
                key for key, bucket in _RATE_LIMIT_BUCKETS.items()
                if not bucket or bucket[-1] <= cutoff
            ]
            for key in stale_keys:
                _RATE_LIMIT_BUCKETS.pop(key, None)
            while len(_RATE_LIMIT_BUCKETS) > _MAX_RATE_LIMIT_BUCKETS:
                _RATE_LIMIT_BUCKETS.pop(next(iter(_RATE_LIMIT_BUCKETS)))

        bucket = _RATE_LIMIT_BUCKETS.setdefault(bucket_key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= rule.limit:
            retry_after = max(1, math.ceil((bucket[0] + rule.window_seconds) - current_time))
            return False, retry_after
        bucket.append(current_time)
        return True, 0


def _rate_limited_response(retry_after: int):
    response, status = _error("Too many requests. Please try again shortly.", 429)
    response.headers["Retry-After"] = str(retry_after)
    return response, status


def _enforce_rate_limit(bucket_key: str, rule_name: str):
    rule = RATE_LIMIT_RULES[rule_name]
    allowed, retry_after = _rate_limit_check(bucket_key, rule)
    if allowed:
        return None
    return _rate_limited_response(retry_after)


def reset_rate_limit_state_for_tests() -> None:
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()


def _handle(handler: Callable[[], dict[str, Any]]):
    try:
        return _ok(handler())
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("Unable to resolve") or message.startswith("Firestore is not configured"):
            return _error(message, 503)
        logging.exception("Logmaxxing API runtime failure")
        return _error("Unable to process Logmaxxing request right now.", 500)
    except Exception:
        logging.exception("Logmaxxing API request failed")
        return _error("Unable to process Logmaxxing request right now.", 500)


def create_fitness_app():
    fitness_app = Flask(__name__)
    fitness_app.url_map.strict_slashes = False

    @fitness_app.before_request
    def attach_firebase_user():
        if request.method == "OPTIONS":
            return Response(status=204)
        ip_limited = _enforce_rate_limit(f"ip:{_client_ip()}", "ip")
        if ip_limited is not None:
            return ip_limited
        try:
            g.auth_user = verify_authorization_header(request.headers.get("Authorization"))
        except AuthError as exc:
            return _error(str(exc), 401)
        user_limited = _enforce_rate_limit(f"user:{g.auth_user['uid']}", "user")
        if user_limited is not None:
            return user_limited
        if request.method == "POST":
            write_limited = _enforce_rate_limit(f"user_write:{g.auth_user['uid']}", "user_write")
            if write_limited is not None:
                return write_limited
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

    @fit_route("/profile/delete-account/", methods=["POST"])
    def fitness_delete_account_api():
        return _handle(
            lambda: delete_account_payload(
                db,
                auth_user=g.auth_user,
                payload=_read_json_body(),
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
