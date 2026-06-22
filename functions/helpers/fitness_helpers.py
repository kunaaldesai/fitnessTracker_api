from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore

from helpers.fitness_profile_helpers import ensure_user_profile

try:
    from google.cloud.firestore_v1.base_query import FieldFilter
except Exception:  # pragma: no cover
    FieldFilter = None

FITNESS_EXERCISES_COLLECTION = "fitness_exercises"
_WRITE_BATCH_LIMIT = 400
MAX_CALENDAR_DAYS = 731
MAX_SETS_PER_EXERCISE = 40
MAX_COPY_EXERCISES = 75
MAX_EXERCISE_WEIGHT_LBS = 2000.0
MAX_EXERCISE_REPS = 1000

CATEGORY_OPTIONS = [
    "Chest",
    "Back",
    "Quads",
    "Hamstrings",
    "Biceps",
    "Triceps",
    "Shoulders",
    "Abs",
    "Cardio",
]

TYPE_OPTIONS = ["Strength", "Cardio"]

MUSCLE_SPLIT_METRIC_OPTIONS = [
    {"key": "total_sets", "label": "Total Sets", "unit": "sets"},
    {"key": "percent_exercises", "label": "% of Exercises", "unit": "%"},
    {"key": "volume", "label": "Volume", "unit": "lbs"},
    {"key": "workout_days", "label": "Workout Days", "unit": "days"},
]
MUSCLE_SPLIT_METRIC_KEYS = {row["key"] for row in MUSCLE_SPLIT_METRIC_OPTIONS}
DEFAULT_MUSCLE_SPLIT_METRIC = "total_sets"
DEFAULT_VOLUME_CATEGORY = "all"

CATEGORY_ALIAS_MAP = {
    "chest": "Chest",
    "back": "Back",
    "quad": "Quads",
    "quads": "Quads",
    "legs": "Quads",
    "hamstring": "Hamstrings",
    "hamstrings": "Hamstrings",
    "bicep": "Biceps",
    "biceps": "Biceps",
    "arms": "Biceps",
    "tricep": "Triceps",
    "triceps": "Triceps",
    "shoulder": "Shoulders",
    "shoulders": "Shoulders",
    "delts": "Shoulders",
    "ab": "Abs",
    "abs": "Abs",
    "core": "Abs",
    "cardio": "Cardio",
    "conditioning": "Cardio",
}

TYPE_ALIAS_MAP = {
    "strength": "Strength",
    "compound": "Strength",
    "isolation": "Strength",
    "cardio": "Cardio",
    "conditioning": "Cardio",
}

DEFAULT_EXERCISE_LIBRARY: list[dict[str, str]] = [
    {"name": "Flat Dumbbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Incline Dumbbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Neutral Grip Pull Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Chin Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Pull Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Dumbbell Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Barbell Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Lat Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Flat Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Incline Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Barbell Back Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Romanian Deadlift", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Leg Press", "category": "Quads", "movement_type": "Strength"},
    {"name": "Conventional Deadlift", "category": "Back", "movement_type": "Strength"},
    {"name": "Sumo Deadlift", "category": "Back", "movement_type": "Strength"},
    {"name": "Overhead Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Seated Dumbbell Shoulder Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Lateral Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Barbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Dumbbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Hammer Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Tricep Pushdown", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Skull Crusher", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Walking Lunge", "category": "Quads", "movement_type": "Strength"},
    {"name": "Leg Extension", "category": "Quads", "movement_type": "Strength"},
    {"name": "Leg Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Hip Thrust", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Standing Calf Raise", "category": "Quads", "movement_type": "Strength"},
    {"name": "Plank", "category": "Abs", "movement_type": "Strength"},
    {"name": "Cable Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Hanging Leg Raise", "category": "Abs", "movement_type": "Strength"},
    {"name": "Machine Chest Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Seated Cable Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Treadmill Run", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Stationary Bike", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Rowing Machine", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Stair Climber", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Jump Rope", "category": "Cardio", "movement_type": "Cardio"},
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _exercise_key(value: Any) -> str:
    return _string(value).casefold()


def _normalize_text(value: Any, *, max_len: int) -> str:
    text = " ".join(_string(value).split())
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _normalize_notes(value: Any, *, max_len: int = 5000) -> str:
    text = _string(value)
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _safe_float(value: Any) -> float | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return max(0.0, parsed)


def _safe_int(value: Any) -> int | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        parsed_float = float(raw)
        if not math.isfinite(parsed_float):
            return None
        parsed = int(parsed_float)
    except (OverflowError, TypeError, ValueError):
        return None
    return max(0, parsed)


def _safe_order(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _parse_iso_date(value: Any) -> date | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def resolve_workout_date(value: Any = None) -> date:
    return _parse_iso_date(value) or _utc_now().date()


def _where_eq(query, field_path: str, value: Any):
    if FieldFilter is not None:
        return query.where(filter=FieldFilter(field_path, "==", value))
    return query.where(field_path, "==", value)


def _normalize_category(value: Any) -> str:
    raw = _normalize_text(value, max_len=80)
    if not raw:
        return ""
    key = raw.casefold()
    if key in CATEGORY_ALIAS_MAP:
        return CATEGORY_ALIAS_MAP[key]
    for option in CATEGORY_OPTIONS:
        if option.casefold() == key:
            return option
    return raw


def _normalize_movement_type(value: Any) -> str:
    raw = _normalize_text(value, max_len=80)
    if not raw:
        return ""
    key = raw.casefold()
    if key in TYPE_ALIAS_MAP:
        return TYPE_ALIAS_MAP[key]
    for option in TYPE_OPTIONS:
        if option.casefold() == key:
            return option
    return raw


def _default_metadata_for_name(name: str) -> dict[str, str] | None:
    lookup_key = _exercise_key(name)
    if not lookup_key:
        return None
    for item in DEFAULT_EXERCISE_LIBRARY:
        if _exercise_key(item.get("name")) == lookup_key:
            return {
                "name": _normalize_text(item.get("name"), max_len=160),
                "category": _normalize_category(item.get("category")),
                "movement_type": _normalize_movement_type(item.get("movement_type")),
            }
    return None


def _coalesce_exercise_metadata(*, name: str, category: Any, movement_type: Any) -> tuple[str, str]:
    normalized_category = _normalize_category(category)
    normalized_type = _normalize_movement_type(movement_type)
    default_meta = _default_metadata_for_name(name)
    if not normalized_category and default_meta:
        normalized_category = default_meta["category"]
    if not normalized_type and default_meta:
        normalized_type = default_meta["movement_type"]
    if normalized_type == "Cardio" and not normalized_category:
        normalized_category = "Cardio"
    if normalized_category == "Cardio":
        normalized_type = "Cardio"
    if not normalized_type:
        normalized_type = "Cardio" if normalized_category == "Cardio" else "Strength"
    return normalized_category, normalized_type


def _normalize_sets(raw_sets: Any, *, validate: bool = False) -> list[dict[str, Any]]:
    if not isinstance(raw_sets, list):
        raw_sets = []
    if len(raw_sets) > MAX_SETS_PER_EXERCISE:
        if validate:
            raise ValueError(f"Exercises can include at most {MAX_SETS_PER_EXERCISE} sets.")
        raw_sets = raw_sets[:MAX_SETS_PER_EXERCISE]
    normalized: list[dict[str, Any]] = []
    for raw_set in raw_sets:
        if not isinstance(raw_set, dict):
            continue
        weight = _safe_float(raw_set.get("weight"))
        reps = _safe_int(raw_set.get("reps"))
        if validate and weight is not None and weight > MAX_EXERCISE_WEIGHT_LBS:
            raise ValueError(f"Set weight must be at most {MAX_EXERCISE_WEIGHT_LBS:g} lbs.")
        if validate and reps is not None and reps > MAX_EXERCISE_REPS:
            raise ValueError(f"Set reps must be at most {MAX_EXERCISE_REPS}.")
        rpe = _safe_float(raw_set.get("rpe"))
        if rpe is not None:
            rpe = max(0.0, min(10.0, rpe))
        normalized.append(
            {
                "weight": min(weight, MAX_EXERCISE_WEIGHT_LBS) if weight is not None else None,
                "reps": min(reps, MAX_EXERCISE_REPS) if reps is not None else None,
                "rpe": rpe,
            }
        )
    return normalized or [{"weight": None, "reps": None, "rpe": None}]


def _set_volume(weight: float | None, reps: int | None) -> float:
    if weight is None or reps is None:
        return 0.0
    return max(0.0, float(weight) * int(reps))


def _set_calculated_one_rm(weight: float | None, reps: int | None) -> float:
    if weight is None or reps is None or weight <= 0 or reps <= 0:
        return 0.0
    return max(0.0, float(weight) * (1.0 + (float(reps) / 30.0)))


def _serialize_exercise(exercise_id: str, data: dict[str, Any]) -> dict[str, Any]:
    serialized_sets: list[dict[str, Any]] = []
    total_volume = 0.0
    completed_sets = 0
    for index, item in enumerate(_normalize_sets(data.get("sets"))):
        weight = _safe_float(item.get("weight"))
        reps = _safe_int(item.get("reps"))
        rpe = _safe_float(item.get("rpe"))
        if rpe is not None:
            rpe = max(0.0, min(10.0, rpe))
        volume = _set_volume(weight, reps)
        if volume > 0:
            completed_sets += 1
        total_volume += volume
        serialized_sets.append(
            {
                "set_number": index + 1,
                "weight": weight,
                "reps": reps,
                "rpe": rpe,
                "volume": round(volume, 2),
                "one_rm": round(_set_calculated_one_rm(weight, reps), 2),
            }
        )

    name = _normalize_text(data.get("name"), max_len=160)
    category, movement_type = _coalesce_exercise_metadata(
        name=name,
        category=data.get("category"),
        movement_type=data.get("movement_type"),
    )
    return {
        "id": exercise_id,
        "owner_uuid": _string(data.get("owner_uuid")),
        "workout_date": _string(data.get("workout_date")),
        "order_index": _safe_order(data.get("order_index")),
        "name": name,
        "category": category,
        "movement_type": movement_type,
        "type": movement_type,
        "notes": _normalize_notes(data.get("notes"), max_len=5000),
        "sets": serialized_sets,
        "total_volume": round(total_volume, 2),
        "completed_sets": completed_sets,
        "created_at_iso": _string(data.get("created_at_iso")),
        "updated_at_iso": _string(data.get("updated_at_iso")),
    }


def _owner_uuid_from_user(db, auth_user: dict[str, Any]) -> tuple[dict[str, Any], str]:
    profile = ensure_user_profile(db, auth_user)
    owner_uuid = _string(profile.get("uuid"))
    if not owner_uuid:
        raise RuntimeError("Unable to resolve user UUID.")
    return profile, owner_uuid


def _next_order_index(db, *, owner_uuid: str, workout_date_iso: str) -> int:
    query = db.collection(FITNESS_EXERCISES_COLLECTION)
    query = _where_eq(query, "owner_uuid", owner_uuid)
    query = _where_eq(query, "workout_date", workout_date_iso)
    max_order = -1
    for snap in query.stream():
        payload = snap.to_dict() or {}
        max_order = max(max_order, _safe_order(payload.get("order_index")))
    return max_order + 1


def _exercise_snapshot_for_owner(db, *, owner_uuid: str, exercise_id: str):
    exercise_ref = db.collection(FITNESS_EXERCISES_COLLECTION).document(exercise_id)
    snap = exercise_ref.get()
    if not snap.exists:
        raise ValueError("Exercise not found.")
    payload = snap.to_dict() or {}
    if _string(payload.get("owner_uuid")) != owner_uuid:
        raise ValueError("Exercise not found.")
    return snap


def list_day_exercises(db, *, owner_uuid: str, workout_date_iso: str) -> list[dict[str, Any]]:
    query = db.collection(FITNESS_EXERCISES_COLLECTION)
    query = _where_eq(query, "owner_uuid", owner_uuid)
    query = _where_eq(query, "workout_date", workout_date_iso)
    exercises = [_serialize_exercise(snap.id, snap.to_dict() or {}) for snap in query.stream()]
    exercises.sort(key=lambda item: (_safe_order(item.get("order_index")), _string(item.get("id"))))
    return exercises


def _list_all_owner_exercises(db, *, owner_uuid: str) -> list[dict[str, Any]]:
    query = _where_eq(db.collection(FITNESS_EXERCISES_COLLECTION), "owner_uuid", owner_uuid)
    exercises = [_serialize_exercise(snap.id, snap.to_dict() or {}) for snap in query.stream()]
    exercises.sort(
        key=lambda item: (
            _string(item.get("workout_date")),
            _safe_order(item.get("order_index")),
            _string(item.get("id")),
        )
    )
    return exercises


def create_exercise(db, *, owner_uuid: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = _normalize_text(payload.get("name"), max_len=160)
    if not name:
        raise ValueError("Exercise name is required.")
    workout_date_iso = resolve_workout_date(payload.get("workout_date")).isoformat()
    category, movement_type = _coalesce_exercise_metadata(
        name=name,
        category=payload.get("category"),
        movement_type=payload.get("movement_type"),
    )
    now_iso = _utc_now_iso()
    exercise_ref = db.collection(FITNESS_EXERCISES_COLLECTION).document()
    doc = {
        "owner_uuid": owner_uuid,
        "workout_date": workout_date_iso,
        "order_index": _next_order_index(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso),
        "name": name,
        "category": category,
        "movement_type": movement_type,
        "notes": _normalize_notes(payload.get("notes"), max_len=5000),
        "sets": _normalize_sets(payload.get("sets"), validate=True),
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "created_at_iso": now_iso,
        "updated_at_iso": now_iso,
    }
    exercise_ref.set(doc, merge=True)
    return _serialize_exercise(exercise_ref.id, doc)


def update_exercise(db, *, owner_uuid: str, exercise_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
    existing = snap.to_dict() or {}
    updates: dict[str, Any] = {}

    next_name = _normalize_text(payload.get("name"), max_len=160) if "name" in payload else _normalize_text(existing.get("name"), max_len=160)
    if "name" in payload and not next_name:
        raise ValueError("Exercise name is required.")
    if "name" in payload:
        updates["name"] = next_name

    if "category" in payload or "movement_type" in payload or "name" in payload:
        category, movement_type = _coalesce_exercise_metadata(
            name=next_name,
            category=payload.get("category") if "category" in payload else existing.get("category"),
            movement_type=payload.get("movement_type") if "movement_type" in payload else existing.get("movement_type"),
        )
        updates["category"] = category
        updates["movement_type"] = movement_type

    if "notes" in payload:
        updates["notes"] = _normalize_notes(payload.get("notes"), max_len=5000)
    if "sets" in payload:
        updates["sets"] = _normalize_sets(payload.get("sets"), validate=True)
    if "workout_date" in payload:
        workout_date_iso = resolve_workout_date(payload.get("workout_date")).isoformat()
        updates["workout_date"] = workout_date_iso
        updates["order_index"] = _next_order_index(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)

    updates["updated_at"] = firestore.SERVER_TIMESTAMP
    updates["updated_at_iso"] = _utc_now_iso()
    snap.reference.set(updates, merge=True)
    merged = dict(existing)
    merged.update(updates)
    return _serialize_exercise(exercise_id, merged)


def delete_exercise(db, *, owner_uuid: str, exercise_id: str) -> None:
    _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id).reference.delete()


def reorder_day_exercises(db, *, owner_uuid: str, workout_date_iso: str, order: list[str]) -> dict[str, Any]:
    if not isinstance(order, list):
        raise ValueError("`order` must be a list of exercise ids.")

    normalized_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in order:
        exercise_id = _string(raw_id)
        if not exercise_id:
            continue
        if exercise_id in seen:
            raise ValueError("Duplicate exercise id in reorder payload.")
        seen.add(exercise_id)
        normalized_ids.append(exercise_id)

    for exercise_id in normalized_ids:
        snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
        if _string((snap.to_dict() or {}).get("workout_date")) != workout_date_iso:
            raise ValueError("Reorder includes an exercise from a different day.")

    batch = db.batch()
    pending = 0
    updates = 0
    now_iso = _utc_now_iso()

    def commit_if_needed(force: bool = False):
        nonlocal batch, pending
        if pending == 0:
            return
        if force or pending >= _WRITE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            pending = 0

    for index, exercise_id in enumerate(normalized_ids):
        exercise_ref = db.collection(FITNESS_EXERCISES_COLLECTION).document(exercise_id)
        batch.set(
            exercise_ref,
            {"order_index": index, "updated_at": firestore.SERVER_TIMESTAMP, "updated_at_iso": now_iso},
            merge=True,
        )
        pending += 1
        updates += 1
        commit_if_needed()
    commit_if_needed(force=True)
    return {"updated": updates}


def _day_labels(workout_date: date) -> dict[str, Any]:
    return {
        "date": workout_date.isoformat(),
        "label_short": f"{workout_date.strftime('%a')}, {workout_date.strftime('%b')} {workout_date.day}",
        "label_full": f"{workout_date.strftime('%A')}, {workout_date.strftime('%b')} {workout_date.day}, {workout_date.year}",
        "is_today": workout_date == _utc_now().date(),
        "weekday": workout_date.strftime("%A"),
        "month_short": workout_date.strftime("%b"),
        "day_of_month": workout_date.day,
        "year": workout_date.year,
        "previous_date": (workout_date - timedelta(days=1)).isoformat(),
        "next_date": (workout_date + timedelta(days=1)).isoformat(),
    }


def _summary_from_exercises(exercises: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_volume": round(sum(float(ex.get("total_volume") or 0) for ex in exercises), 2),
        "sets_completed": sum(int(ex.get("completed_sets") or 0) for ex in exercises),
        "exercise_count": len(exercises),
    }


def build_day_payload(db, *, auth_user: dict[str, Any], workout_date: Any = None) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    selected_date = resolve_workout_date(workout_date)
    exercises = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=selected_date.isoformat())
    return {
        "user": profile,
        "day": _day_labels(selected_date),
        "summary": _summary_from_exercises(exercises),
        "exercises": exercises,
    }


def list_exercise_options(db, *, auth_user: dict[str, Any]) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    merged: dict[str, dict[str, Any]] = {}
    for item in DEFAULT_EXERCISE_LIBRARY:
        name = _normalize_text(item.get("name"), max_len=160)
        category, movement_type = _coalesce_exercise_metadata(name=name, category=item.get("category"), movement_type=item.get("movement_type"))
        merged[_exercise_key(name)] = {"name": name, "category": category, "movement_type": movement_type, "type": movement_type, "source": "default", "_rank": ""}
    for exercise in _list_all_owner_exercises(db, owner_uuid=owner_uuid):
        name = _normalize_text(exercise.get("name"), max_len=160)
        if not name:
            continue
        key = _exercise_key(name)
        category, movement_type = _coalesce_exercise_metadata(name=name, category=exercise.get("category"), movement_type=exercise.get("movement_type"))
        rank = _string(exercise.get("updated_at_iso")) or _string(exercise.get("workout_date"))
        existing = merged.get(key)
        if existing is None or rank >= _string(existing.get("_rank")):
            merged[key] = {"name": name, "category": category, "movement_type": movement_type, "type": movement_type, "source": "custom", "_rank": rank}

    exercises = sorted(
        [
            {
                "name": item["name"],
                "category": item["category"],
                "movement_type": item["movement_type"],
                "type": item["movement_type"],
                "source": item.get("source") or "custom",
            }
            for item in merged.values()
        ],
        key=lambda row: (_exercise_key(row.get("name")), row.get("name")),
    )
    return {"user": profile, "categories": list(CATEGORY_OPTIONS), "types": list(TYPE_OPTIONS), "exercises": exercises, "default_count": len(DEFAULT_EXERCISE_LIBRARY)}


def resolve_analytics_range(*, range_key: Any = None, start_date: Any = None, end_date: Any = None) -> dict[str, Any]:
    today = _utc_now().date()
    key = _string(range_key).lower() or "3m"
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if start or end:
        start = start or date(today.year, 1, 1)
        end = end or today
        if start > end:
            start, end = end, start
        return {"key": "custom", "start_date": start.isoformat(), "end_date": end.isoformat()}
    if key == "1m":
        start, end = today - timedelta(days=30), today
    elif key == "3m":
        start, end = today - timedelta(days=90), today
    elif key == "6m":
        start, end = today - timedelta(days=180), today
    elif key == "ytd":
        start, end = date(today.year, 1, 1), today
    else:
        key, start, end = "all", None, None
    return {"key": key, "start_date": start.isoformat() if start else None, "end_date": end.isoformat() if end else None}


def _exercise_metrics(exercise: dict[str, Any]) -> dict[str, Any]:
    total_volume = 0.0
    completed_sets = 0
    max_weight = 0.0
    max_one_rm = 0.0
    best_set = {"weight": None, "reps": None, "rpe": None, "volume": 0.0, "one_rm": 0.0}
    for set_row in exercise.get("sets") or []:
        weight = _safe_float(set_row.get("weight"))
        reps = _safe_int(set_row.get("reps"))
        rpe = _safe_float(set_row.get("rpe"))
        volume = _set_volume(weight, reps)
        one_rm = _set_calculated_one_rm(weight, reps)
        if volume > 0:
            completed_sets += 1
            total_volume += volume
        if weight is not None:
            max_weight = max(max_weight, float(weight))
        if one_rm > max_one_rm:
            max_one_rm = one_rm
            best_set = {"weight": weight, "reps": reps, "rpe": rpe, "volume": round(volume, 2), "one_rm": round(one_rm, 2)}
    return {
        "total_volume": round(total_volume, 2),
        "completed_sets": completed_sets,
        "max_weight": round(max_weight, 2),
        "max_one_rm": round(max_one_rm, 2),
        "best_set": best_set,
    }


def _filter_exercises_by_range(exercises: list[dict[str, Any]], *, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
    if start_date is None and end_date is None:
        return list(exercises)
    output = []
    for exercise in exercises:
        workout_date = _parse_iso_date(exercise.get("workout_date"))
        if workout_date is None:
            continue
        if start_date and workout_date < start_date:
            continue
        if end_date and workout_date > end_date:
            continue
        output.append(exercise)
    return output


def _format_date_short(iso_date: str) -> str:
    parsed = _parse_iso_date(iso_date)
    if parsed is None:
        return iso_date
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def _best_set_label(best_set: dict[str, Any] | None) -> str:
    if not isinstance(best_set, dict):
        return "-"
    weight = _safe_float(best_set.get("weight"))
    reps = _safe_int(best_set.get("reps"))
    if weight is not None and reps is not None and reps > 0:
        return f"{round(weight, 2):g} lbs x {int(reps)}"
    if reps is not None and reps > 0:
        return f"{int(reps)} reps"
    return "-"


def _aggregate_records(exercises: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for exercise in exercises:
        name = _normalize_text(exercise.get("name"), max_len=160)
        workout_date_iso = _string(exercise.get("workout_date"))
        workout_date = _parse_iso_date(workout_date_iso)
        if not name or workout_date is None:
            continue
        category, movement_type = _coalesce_exercise_metadata(name=name, category=exercise.get("category"), movement_type=exercise.get("movement_type"))
        metrics = _exercise_metrics(exercise)
        key = _exercise_key(name)
        bucket = grouped.setdefault(
            key,
            {
                "exercise_name": name,
                "category": category,
                "movement_type": movement_type,
                "sessions": [],
                "max_weight": 0.0,
                "max_weight_date": None,
                "max_one_rm": 0.0,
                "max_one_rm_date": None,
                "max_volume": 0.0,
                "max_volume_date": None,
            },
        )
        bucket["sessions"].append(
            {
                "date": workout_date_iso,
                "date_obj": workout_date,
                "total_volume": metrics["total_volume"],
                "max_weight": metrics["max_weight"],
                "max_one_rm": metrics["max_one_rm"],
                "best_set": metrics["best_set"],
                "completed_sets": metrics["completed_sets"],
            }
        )
        if metrics["max_weight"] >= float(bucket["max_weight"]):
            bucket["max_weight"], bucket["max_weight_date"] = round(metrics["max_weight"], 2), workout_date_iso
        if metrics["max_one_rm"] >= float(bucket["max_one_rm"]):
            bucket["max_one_rm"], bucket["max_one_rm_date"] = round(metrics["max_one_rm"], 2), workout_date_iso
        if metrics["total_volume"] >= float(bucket["max_volume"]):
            bucket["max_volume"], bucket["max_volume_date"] = round(metrics["total_volume"], 2), workout_date_iso

    records: list[dict[str, Any]] = []
    for bucket in grouped.values():
        sessions = sorted(bucket["sessions"], key=lambda item: (item["date_obj"], item["date"]))
        if not sessions:
            continue
        latest = sessions[-1]
        previous = sessions[-2] if len(sessions) > 1 else None
        first_one_rm = float(sessions[0].get("max_one_rm") or 0)
        latest_one_rm = float(latest.get("max_one_rm") or 0)
        previous_one_rm = float(previous.get("max_one_rm") or 0) if previous else 0.0
        records.append(
            {
                "exercise_name": bucket["exercise_name"],
                "category": bucket["category"],
                "movement_type": bucket["movement_type"],
                "type": bucket["movement_type"],
                "max_weight": round(float(bucket["max_weight"]), 2),
                "max_weight_date": bucket["max_weight_date"],
                "max_weight_date_label": _format_date_short(bucket["max_weight_date"] or ""),
                "max_one_rm": round(float(bucket["max_one_rm"]), 2),
                "max_one_rm_date": bucket["max_one_rm_date"],
                "max_one_rm_date_label": _format_date_short(bucket["max_one_rm_date"] or ""),
                "max_volume": round(float(bucket["max_volume"]), 2),
                "max_volume_date": bucket["max_volume_date"],
                "max_volume_date_label": _format_date_short(bucket["max_volume_date"] or ""),
                "latest_one_rm": round(latest_one_rm, 2),
                "previous_one_rm": round(previous_one_rm, 2),
                "one_rm_delta": round(latest_one_rm - previous_one_rm, 2),
                "improvement_since_first": round(latest_one_rm - first_one_rm, 2),
                "last_workout_date": latest.get("date"),
                "last_workout_date_label": _format_date_short(latest.get("date") or ""),
                "latest_volume": round(float(latest.get("total_volume") or 0), 2),
                "latest_best_set": latest.get("best_set") or {},
                "session_count": len(sessions),
            }
        )
    records.sort(key=lambda item: (-float(item.get("max_one_rm") or 0), item.get("exercise_name") or ""))
    return records


def _build_volume_progression(exercises: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, float] = defaultdict(float)
    for exercise in exercises:
        workout_date_iso = _string(exercise.get("workout_date"))
        if workout_date_iso:
            by_date[workout_date_iso] += float(_exercise_metrics(exercise).get("total_volume") or 0)
    return [
        {"date": workout_date_iso, "date_label": _format_date_short(workout_date_iso), "volume": round(by_date[workout_date_iso], 2)}
        for workout_date_iso in sorted(by_date.keys())
    ]


def _exercise_category_label(exercise: dict[str, Any]) -> str:
    return _normalize_category(exercise.get("category")) or "Other"


def _normalize_volume_category(value: Any) -> str:
    raw = _string(value)
    if not raw or raw.casefold() in {"all", "*", "any", "all_categories"}:
        return DEFAULT_VOLUME_CATEGORY
    return _normalize_category(raw) or DEFAULT_VOLUME_CATEGORY


def _filter_exercises_by_category(exercises: list[dict[str, Any]], *, category: Any = None) -> list[dict[str, Any]]:
    normalized_category = _normalize_volume_category(category)
    if normalized_category == DEFAULT_VOLUME_CATEGORY:
        return list(exercises)
    return [exercise for exercise in exercises if _exercise_category_label(exercise) == normalized_category]


def _build_volume_category_options(exercises: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels = sorted({_exercise_category_label(exercise) for exercise in exercises if _exercise_category_label(exercise)})
    return [{"key": DEFAULT_VOLUME_CATEGORY, "label": "All categories"}, *[{"key": label, "label": label} for label in labels]]


def _normalize_muscle_split_metric(value: Any) -> str:
    key = _string(value).casefold().replace("-", "_").replace(" ", "_")
    key = {
        "percent": "percent_exercises",
        "sets": "total_sets",
        "days": "workout_days",
        "set_count": "total_sets",
        "exercise_pct": "percent_exercises",
    }.get(key, key)
    return key if key in MUSCLE_SPLIT_METRIC_KEYS else DEFAULT_MUSCLE_SPLIT_METRIC


def _build_muscle_split(exercises: list[dict[str, Any]], *, metric: Any = None) -> list[dict[str, Any]]:
    metric_key = _normalize_muscle_split_metric(metric)
    by_group: dict[str, float] = defaultdict(float)
    by_group_days: dict[str, set[str]] = defaultdict(set)
    for exercise in exercises:
        category = _normalize_category(exercise.get("category")) or "Other"
        metrics = _exercise_metrics(exercise)
        if metric_key == "volume":
            by_group[category] += float(metrics.get("total_volume") or 0)
        elif metric_key == "total_sets":
            by_group[category] += float(metrics.get("completed_sets") or 0)
        elif metric_key == "workout_days":
            workout_date = _string(exercise.get("workout_date"))
            if workout_date:
                by_group_days[category].add(workout_date)
        else:
            by_group[category] += 1.0
    if metric_key == "workout_days":
        by_group = defaultdict(float, {group: float(len(days)) for group, days in by_group_days.items()})
    total = sum(by_group.values())
    if total <= 0:
        return []
    unit_by_metric = {"percent_exercises": "exercises", "total_sets": "sets", "volume": "lbs", "workout_days": "days"}
    split = []
    for group, raw_value in by_group.items():
        value = round(float(raw_value), 2) if metric_key == "volume" else int(round(float(raw_value)))
        split.append({"group": group, "value": value, "percent": round((float(raw_value) / total) * 100.0, 1), "metric": metric_key, "unit": unit_by_metric.get(metric_key, "")})
    split.sort(key=lambda item: (-float(item.get("percent") or 0), item.get("group") or ""))
    return split


def _build_recent_activity(exercises: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    for exercise in exercises:
        workout_date_iso = _string(exercise.get("workout_date"))
        workout_date = _parse_iso_date(workout_date_iso)
        if workout_date is None:
            continue
        metrics = _exercise_metrics(exercise)
        rows.append(
            {
                "exercise_id": _string(exercise.get("id")),
                "exercise_name": _normalize_text(exercise.get("name"), max_len=160),
                "category": _normalize_category(exercise.get("category")) or "Other",
                "movement_type": _normalize_movement_type(exercise.get("movement_type")) or "Strength",
                "date": workout_date_iso,
                "date_label": _format_date_short(workout_date_iso),
                "sets_completed": int(metrics.get("completed_sets") or 0),
                "best_set_label": _best_set_label(metrics.get("best_set")),
                "volume": round(float(metrics.get("total_volume") or 0), 2),
                "max_one_rm": round(float(metrics.get("max_one_rm") or 0), 2),
                "order_index": _safe_order(exercise.get("order_index")),
            }
        )
    rows.sort(key=lambda row: (_parse_iso_date(row.get("date")) or date.min, row.get("order_index") or 0, row.get("exercise_name") or ""), reverse=True)
    return rows[: max(1, int(limit))]


def build_analytics_payload(
    db,
    *,
    auth_user: dict[str, Any],
    range_key: Any = None,
    start_date: Any = None,
    end_date: Any = None,
    muscle_split_metric: Any = None,
    volume_category: Any = None,
) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    all_exercises = _list_all_owner_exercises(db, owner_uuid=owner_uuid)
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    start = _parse_iso_date(range_payload.get("start_date"))
    end = _parse_iso_date(range_payload.get("end_date"))
    filtered = _filter_exercises_by_range(all_exercises, start_date=start, end_date=end)
    records = _aggregate_records(filtered)

    volume_category_options = _build_volume_category_options(all_exercises)
    normalized_volume_category = _normalize_volume_category(volume_category)
    allowed_categories = {row["key"] for row in volume_category_options}
    if normalized_volume_category not in allowed_categories:
        normalized_volume_category = DEFAULT_VOLUME_CATEGORY

    volume_progression_by_category: dict[str, list[dict[str, Any]]] = {}
    for option in volume_category_options:
        category_key = _string(option.get("key")) or DEFAULT_VOLUME_CATEGORY
        category_filtered = _filter_exercises_by_category(filtered, category=category_key)
        volume_progression_by_category[category_key] = _build_volume_progression(category_filtered)
    volume_progression = volume_progression_by_category.get(normalized_volume_category, [])
    total_volume = round(sum(float(item.get("volume") or 0) for item in volume_progression), 2)

    total_sets = 0
    workout_days: set[str] = set()
    exercise_names: set[str] = set()
    for exercise in filtered:
        workout_days.add(_string(exercise.get("workout_date")))
        exercise_names.add(_normalize_text(exercise.get("name"), max_len=160))
        total_sets += int(_exercise_metrics(exercise).get("completed_sets") or 0)

    muscle_split_by_metric = {
        _string(option["key"]): _build_muscle_split(filtered, metric=option["key"])
        for option in MUSCLE_SPLIT_METRIC_OPTIONS
    }
    normalized_split_metric = _normalize_muscle_split_metric(muscle_split_metric)
    return {
        "user": profile,
        "range": range_payload,
        "summary": {
            "total_volume": total_volume,
            "sets_completed": total_sets,
            "exercise_count": len([name for name in exercise_names if name]),
            "workout_days": len([day for day in workout_days if day]),
            "record_count": len(records),
        },
        "personal_records": records[:3],
        "personal_records_total": len(records),
        "volume_progression": volume_progression,
        "volume_progression_by_category": volume_progression_by_category,
        "volume_totals": {"current": total_volume, "previous": 0.0},
        "volume_totals_by_category": {
            key: {"current": round(sum(float(item.get("volume") or 0) for item in rows), 2), "previous": 0.0}
            for key, rows in volume_progression_by_category.items()
        },
        "volume_category": normalized_volume_category,
        "volume_category_options": volume_category_options,
        "muscle_split_metric": normalized_split_metric,
        "muscle_split_metrics": MUSCLE_SPLIT_METRIC_OPTIONS,
        "muscle_split": muscle_split_by_metric.get(normalized_split_metric, []),
        "muscle_split_by_metric": muscle_split_by_metric,
        "recent_activity": _build_recent_activity(filtered, limit=25),
    }


def _sort_records(records: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    if sort_key == "date":
        return sorted(records, key=lambda item: (_parse_iso_date(item.get("last_workout_date")) or date.min, item.get("exercise_name") or ""), reverse=True)
    if sort_key == "weight":
        return sorted(records, key=lambda item: (float(item.get("max_weight") or 0), item.get("exercise_name") or ""), reverse=True)
    if sort_key == "volume":
        return sorted(records, key=lambda item: (float(item.get("max_volume") or 0), item.get("exercise_name") or ""), reverse=True)
    if sort_key == "onerm":
        return sorted(records, key=lambda item: (float(item.get("max_one_rm") or 0), item.get("exercise_name") or ""), reverse=True)
    return sorted(records, key=lambda item: (_exercise_key(item.get("exercise_name")), item.get("exercise_name") or ""))


def build_records_payload(
    db,
    *,
    auth_user: dict[str, Any],
    query: Any = None,
    sort_key: Any = None,
    page: int = 1,
    page_size: int = 24,
    range_key: Any = None,
    start_date: Any = None,
    end_date: Any = None,
) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    all_exercises = _list_all_owner_exercises(db, owner_uuid=owner_uuid)
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    filtered = _filter_exercises_by_range(
        all_exercises,
        start_date=_parse_iso_date(range_payload.get("start_date")),
        end_date=_parse_iso_date(range_payload.get("end_date")),
    )
    records = _aggregate_records(filtered)
    search = _string(query).casefold()
    if search:
        records = [
            row for row in records
            if search in _exercise_key(row.get("exercise_name"))
            or search in _exercise_key(row.get("category"))
            or search in _exercise_key(row.get("movement_type"))
        ]
    normalized_sort = _string(sort_key).lower() or "name"
    records = _sort_records(records, normalized_sort)
    safe_page_size = max(1, min(100, int(page_size or 24)))
    safe_page = max(1, int(page or 1))
    total_items = len(records)
    total_pages = max(1, ((total_items - 1) // safe_page_size) + 1) if total_items else 1
    safe_page = min(safe_page, total_pages)
    page_records = records[(safe_page - 1) * safe_page_size:(safe_page - 1) * safe_page_size + safe_page_size]

    recent_cutoff = _utc_now().date() - timedelta(days=30)
    new_prs_30d = sum(1 for record in records if (_parse_iso_date(record.get("max_one_rm_date")) or date.min) >= recent_cutoff)
    strongest_lift = max(records, key=lambda item: float(item.get("max_weight") or 0), default=None)
    improved_records = [record for record in records if int(record.get("session_count") or 0) > 1 and float(record.get("improvement_since_first") or 0) > 0]
    most_improved = max(improved_records, key=lambda item: float(item.get("improvement_since_first") or 0), default=None)
    return {
        "user": profile,
        "range": range_payload,
        "query": _string(query),
        "sort": normalized_sort,
        "paging": {
            "page": safe_page,
            "page_size": safe_page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": safe_page < total_pages,
            "has_previous": safe_page > 1,
        },
        "summary": {
            "total_exercises": total_items,
            "new_prs_30d": new_prs_30d,
            "strongest_lift": {"exercise_name": strongest_lift.get("exercise_name"), "max_weight": strongest_lift.get("max_weight")} if strongest_lift else None,
            "most_improved": {"exercise_name": most_improved.get("exercise_name"), "improvement_since_first": most_improved.get("improvement_since_first")} if most_improved else None,
        },
        "records": page_records,
    }


def _get_last_sessions_before(db, *, owner_uuid: str, before_date_iso: str, exercise_names: list[str]) -> dict[str, Any]:
    before_date = _parse_iso_date(before_date_iso)
    if not exercise_names or before_date is None:
        return {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ex in _list_all_owner_exercises(db, owner_uuid=owner_uuid):
        ex_date = _parse_iso_date(_string(ex.get("workout_date")))
        if ex_date is not None and ex_date < before_date:
            by_name[_exercise_key(ex.get("name"))].append(ex)
    result = {}
    for name in exercise_names:
        sessions = by_name.get(_exercise_key(name), [])
        if not sessions:
            continue
        latest = max(sessions, key=lambda item: _string(item.get("workout_date")))
        parts = []
        for set_row in latest.get("sets") or []:
            weight = _safe_float(set_row.get("weight"))
            reps = _safe_int(set_row.get("reps"))
            if weight is not None and reps is not None and reps > 0:
                parts.append(f"{weight:g}x{reps}")
            elif reps is not None and reps > 0:
                parts.append(f"{reps} reps")
        result[name] = {"date": _string(latest.get("workout_date")), "date_label": _format_date_short(_string(latest.get("workout_date"))), "sets_summary": parts}
    return result


def build_last_sessions_payload(db, *, auth_user: dict[str, Any], date_iso: Any = None) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    date_obj = resolve_workout_date(date_iso)
    day_exercises = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=date_obj.isoformat())
    names = list({_normalize_text(ex.get("name"), max_len=160) for ex in day_exercises if ex.get("name")})
    return {"user": profile, "last_sessions": _get_last_sessions_before(db, owner_uuid=owner_uuid, before_date_iso=date_obj.isoformat(), exercise_names=names)}


def build_previous_workout_payload(db, *, auth_user: dict[str, Any], before_date: Any = None) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    before = resolve_workout_date(before_date)
    candidates = []
    for ex in _list_all_owner_exercises(db, owner_uuid=owner_uuid):
        ex_date = _parse_iso_date(_string(ex.get("workout_date")))
        if ex_date is not None and ex_date < before:
            candidates.append(ex)
    if not candidates:
        return {"user": profile, "previous_date": None, "previous_date_label": None, "exercises": []}
    candidates.sort(key=lambda ex: (_string(ex.get("workout_date")), _string(ex.get("updated_at_iso")), _safe_order(ex.get("order_index")), _string(ex.get("id"))), reverse=True)
    prev_exercises = []
    seen_names: set[str] = set()
    for ex in candidates:
        name = _normalize_text(ex.get("name"), max_len=160)
        key = _exercise_key(name)
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        source_date = _string(ex.get("workout_date"))
        prev_exercises.append({**ex, "name": name, "source_date": source_date, "source_date_label": _format_date_short(source_date)})
    if not prev_exercises:
        return {"user": profile, "previous_date": None, "previous_date_label": None, "exercises": []}
    previous_date = _string(prev_exercises[0].get("source_date"))
    return {"user": profile, "previous_date": previous_date, "previous_date_label": _format_date_short(previous_date), "exercises": prev_exercises}


def copy_exercises_from_date_payload(db, *, auth_user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    target_date_iso = resolve_workout_date(payload.get("target_date")).isoformat()
    source_exercises: list[dict[str, Any]] = []
    raw_ids = payload.get("exercise_ids")
    if raw_ids is not None:
        if not isinstance(raw_ids, list):
            raise ValueError("exercise_ids must be a list.")
        if len(raw_ids) > MAX_COPY_EXERCISES:
            raise ValueError(f"You can copy at most {MAX_COPY_EXERCISES} exercises at once.")
        seen_ids: set[str] = set()
        for raw_id in raw_ids:
            exercise_id = _string(raw_id)
            if not exercise_id or exercise_id in seen_ids:
                continue
            seen_ids.add(exercise_id)
            if len(seen_ids) > MAX_COPY_EXERCISES:
                raise ValueError(f"You can copy at most {MAX_COPY_EXERCISES} exercises at once.")
            snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
            source_exercises.append(_serialize_exercise(snap.id, snap.to_dict() or {}))
    else:
        source_date = _parse_iso_date(payload.get("source_date"))
        if source_date is None:
            raise ValueError("exercise_ids or source_date is required.")
        if source_date.isoformat() == target_date_iso:
            raise ValueError("Cannot copy a workout onto the same date.")
        source_exercises = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=source_date.isoformat())

    if len(source_exercises) > MAX_COPY_EXERCISES:
        raise ValueError(f"You can copy at most {MAX_COPY_EXERCISES} exercises at once.")
    if any(_string(ex.get("workout_date")) == target_date_iso for ex in source_exercises):
        raise ValueError("Cannot copy an exercise onto the same date.")
    created = []
    for ex in source_exercises:
        raw_sets = [{"weight": _safe_float(s.get("weight")), "reps": _safe_int(s.get("reps")), "rpe": _safe_float(s.get("rpe"))} for s in (ex.get("sets") or [])]
        created.append(
            create_exercise(
                db,
                owner_uuid=owner_uuid,
                payload={"name": ex.get("name"), "category": ex.get("category"), "movement_type": ex.get("movement_type"), "notes": "", "workout_date": target_date_iso, "sets": raw_sets},
            )
        )
    return {"user": profile, "created": created, "count": len(created)}


def build_exercise_history_payload(db, *, auth_user: dict[str, Any], exercise_name: Any) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    name = _normalize_text(exercise_name, max_len=160)
    if not name:
        raise ValueError("exercise_name is required.")
    name_key = _exercise_key(name)
    category = ""
    movement_type = ""
    sessions = []
    for ex in _list_all_owner_exercises(db, owner_uuid=owner_uuid):
        if _exercise_key(ex.get("name")) != name_key:
            continue
        metrics = _exercise_metrics(ex)
        sessions.append(
            {
                "date": _string(ex.get("workout_date")),
                "date_label": _format_date_short(_string(ex.get("workout_date"))),
                "sets_completed": int(metrics.get("completed_sets") or 0),
                "best_set_label": _best_set_label(metrics.get("best_set")),
                "volume": round(float(metrics.get("total_volume") or 0), 2),
                "max_one_rm": round(float(metrics.get("max_one_rm") or 0), 2),
                "max_weight": round(float(metrics.get("max_weight") or 0), 2),
            }
        )
        if not category:
            category, movement_type = _coalesce_exercise_metadata(name=name, category=ex.get("category"), movement_type=ex.get("movement_type"))
    sessions.sort(key=lambda item: item.get("date") or "")
    return {"user": profile, "exercise_name": name, "category": category, "movement_type": movement_type, "sessions": sessions, "session_count": len(sessions)}


def _compute_streaks(workout_date_set: set[date]) -> tuple[int, int]:
    if not workout_date_set:
        return 0, 0
    today = _utc_now().date()
    current = 0
    check = today
    while check in workout_date_set:
        current += 1
        check -= timedelta(days=1)
    if current == 0:
        check = today - timedelta(days=1)
        while check in workout_date_set:
            current += 1
            check -= timedelta(days=1)
    sorted_dates = sorted(workout_date_set)
    longest = 1
    temp = 1
    for index in range(1, len(sorted_dates)):
        if (sorted_dates[index] - sorted_dates[index - 1]).days == 1:
            temp += 1
            longest = max(longest, temp)
        else:
            temp = 1
    return current, max(longest, temp)


def build_workout_calendar_payload(db, *, auth_user: dict[str, Any], range_key: Any = None, start_date: Any = None, end_date: Any = None) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    all_exercises = _list_all_owner_exercises(db, owner_uuid=owner_uuid)
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    start = _parse_iso_date(range_payload.get("start_date"))
    end = _parse_iso_date(range_payload.get("end_date")) or _utc_now().date()
    filtered = _filter_exercises_by_range(all_exercises, start_date=start, end_date=end)
    by_date: dict[str, float] = defaultdict(float)
    for ex in filtered:
        date_iso = _string(ex.get("workout_date"))
        if date_iso:
            by_date[date_iso] += float(_exercise_metrics(ex).get("total_volume") or 0)
    if start is None:
        workout_dates = [parsed for iso in by_date if (parsed := _parse_iso_date(iso)) is not None]
        start = min(workout_dates) if workout_dates else end
    if (end - start).days + 1 > MAX_CALENDAR_DAYS:
        if _string(range_payload.get("key")) == "custom":
            raise ValueError(f"Workout calendar range cannot exceed {MAX_CALENDAR_DAYS} days.")
        start = end - timedelta(days=MAX_CALENDAR_DAYS - 1)
    grid_start = start - timedelta(days=start.weekday())
    max_volume = max(by_date.values()) if by_date else 1.0
    weeks: list[list[dict[str, Any]]] = []
    current_day = grid_start
    week: list[dict[str, Any]] = []
    while current_day <= end:
        date_iso = current_day.isoformat()
        volume = round(by_date.get(date_iso, 0.0), 2)
        has_workout = date_iso in by_date
        ratio = volume / max_volume if has_workout and max_volume > 0 else 0
        level = 0 if not has_workout else 1 if ratio < 0.15 else 2 if ratio < 0.4 else 3 if ratio < 0.7 else 4
        week.append({"date": date_iso, "volume": volume, "has_workout": has_workout, "level": level})
        if len(week) == 7:
            weeks.append(week)
            week = []
        current_day += timedelta(days=1)
    if week:
        while len(week) < 7:
            week.append({"date": None, "volume": 0.0, "has_workout": False, "level": 0})
        weeks.append(week)
    workout_date_objects = {d for iso in by_date if (d := _parse_iso_date(iso)) is not None}
    current_streak, longest_streak = _compute_streaks(workout_date_objects)
    return {
        "user": profile,
        "range": range_payload,
        "weeks": weeks,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_workout_days": len(by_date),
        "max_volume": round(max_volume, 2),
    }


def create_fitness_exercise(db, *, auth_user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    return {"exercise": create_exercise(db, owner_uuid=owner_uuid, payload=payload or {}), "user": profile}


def update_fitness_exercise(db, *, auth_user: dict[str, Any], exercise_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    return {"exercise": update_exercise(db, owner_uuid=owner_uuid, exercise_id=_string(exercise_id), payload=payload or {}), "user": profile}


def delete_fitness_exercise(db, *, auth_user: dict[str, Any], exercise_id: str) -> dict[str, Any]:
    _, owner_uuid = _owner_uuid_from_user(db, auth_user)
    normalized_id = _string(exercise_id)
    delete_exercise(db, owner_uuid=owner_uuid, exercise_id=normalized_id)
    return {"deleted": True, "exercise_id": normalized_id}


def reorder_fitness_exercises(db, *, auth_user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    _, owner_uuid = _owner_uuid_from_user(db, auth_user)
    workout_date_iso = resolve_workout_date((payload or {}).get("workout_date")).isoformat()
    return {
        "reordered": reorder_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso, order=(payload or {}).get("order") or []),
        "workout_date": workout_date_iso,
    }
