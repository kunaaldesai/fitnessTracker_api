from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore

USERS_COLLECTION = "users"
WEIGHT_ENTRIES_COLLECTION = "weight_entries"

DEFAULT_BMR_FORMULA = "katch_mcardle"
DEFAULT_ACTIVITY_LEVEL = "sedentary"
BMI_VISUAL_MIN = 15.0
BMI_VISUAL_MAX = 40.0
CUSTOM_GOAL_MIN = -2.0
CUSTOM_GOAL_MAX = 2.0
KG_PER_LB = 0.45359237
LB_PER_KG = 1 / KG_PER_LB

ACTIVITY_LEVEL_OPTIONS = [
    {"key": "sedentary", "label": "Sedentary", "multiplier": 1.2, "description": "Little or no exercise"},
    {"key": "lightly_active", "label": "Lightly Active", "multiplier": 1.375, "description": "Light exercise 1-3 days per week"},
    {"key": "moderately_active", "label": "Moderately Active", "multiplier": 1.55, "description": "Moderate exercise 3-5 days per week"},
    {"key": "very_active", "label": "Very Active", "multiplier": 1.725, "description": "Hard exercise 6-7 days per week"},
    {"key": "extra_active", "label": "Extra Active", "multiplier": 1.9, "description": "Twice-daily training or physical job"},
]

BMR_FORMULA_OPTIONS = [
    {"key": "katch_mcardle", "label": "Katch-McArdle Formula", "description": "Uses weight and body-fat percentage."},
    {"key": "mifflin_st_jeor", "label": "Mifflin-St Jeor Equation", "description": "Uses date of birth, sex, height, and weight."},
    {"key": "harris_benedict", "label": "Harris-Benedict Equation", "description": "Uses date of birth, sex, height, and weight with the Harris-Benedict formula."},
]

CALORIE_TARGET_PRESETS = [
    ("cut_1_lb", -1.0, "-1 lb / week"),
    ("cut_half_lb", -0.5, "-0.5 lb / week"),
    ("maintain", 0.0, "Maintain"),
    ("gain_half_lb", 0.5, "+0.5 lb / week"),
    ("gain_1_lb", 1.0, "+1 lb / week"),
]

ACTIVITY_LEVEL_MAP = {item["key"]: item for item in ACTIVITY_LEVEL_OPTIONS}
BMR_FORMULA_MAP = {item["key"]: item for item in BMR_FORMULA_OPTIONS}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_name(value: Any, *, max_len: int = 150) -> str:
    text = " ".join(_string(value).split())
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _parse_iso_date(value: Any) -> date | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        parsed = float(raw)
        if not math.isfinite(parsed):
            return None
        return int(parsed)
    except (OverflowError, TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        parsed = float(raw)
        if not math.isfinite(parsed):
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _round_or_none(value: float | None, digits: int = 2):
    if value is None:
        return None
    return round(float(value), digits)


def _normalize_activity_level(value: Any) -> str:
    key = _string(value).lower().replace("-", "_").replace(" ", "_")
    return key if key in ACTIVITY_LEVEL_MAP else DEFAULT_ACTIVITY_LEVEL


def _normalize_bmr_formula(value: Any) -> str:
    key = _string(value).lower().replace("-", "_").replace(" ", "_")
    return key if key in BMR_FORMULA_MAP else DEFAULT_BMR_FORMULA


def _normalize_sex_for_bmr(value: Any) -> str:
    key = _string(value).lower()
    return key if key in {"male", "female"} else ""


def _default_profile(now_iso: str | None = None) -> dict[str, Any]:
    timestamp = now_iso or _utc_now_iso()
    return {
        "date_of_birth": None,
        "sex_for_bmr": "",
        "height_feet": None,
        "height_inches": None,
        "weight_lbs": None,
        "target_weight_lbs": None,
        "activity_level": DEFAULT_ACTIVITY_LEVEL,
        "bmr_formula": DEFAULT_BMR_FORMULA,
        "body_fat_percent": None,
        "custom_goal_lbs_per_week": None,
        "weight_history_initialized": False,
        "created_at_iso": timestamp,
        "updated_at_iso": timestamp,
    }


def _serialize_profile(raw_profile: Any) -> dict[str, Any]:
    profile = _default_profile()
    if isinstance(raw_profile, dict):
        profile.update(raw_profile)
    profile["activity_level"] = _normalize_activity_level(profile.get("activity_level"))
    profile["bmr_formula"] = _normalize_bmr_formula(profile.get("bmr_formula"))
    profile["sex_for_bmr"] = _normalize_sex_for_bmr(profile.get("sex_for_bmr"))
    profile["height_feet"] = _parse_int(profile.get("height_feet"))
    profile["height_inches"] = _parse_int(profile.get("height_inches"))
    profile["weight_lbs"] = _round_or_none(_parse_float(profile.get("weight_lbs")))
    profile["target_weight_lbs"] = _round_or_none(_parse_float(profile.get("target_weight_lbs")))
    profile["body_fat_percent"] = _round_or_none(_parse_float(profile.get("body_fat_percent")))
    profile["custom_goal_lbs_per_week"] = _round_or_none(_parse_float(profile.get("custom_goal_lbs_per_week")))
    profile["weight_history_initialized"] = bool(profile.get("weight_history_initialized"))
    parsed_dob = _parse_iso_date(profile.get("date_of_birth"))
    profile["date_of_birth"] = parsed_dob.isoformat() if parsed_dob else None
    return profile


def _split_display_name(display_name: str) -> tuple[str, str]:
    parts = [part for part in _string(display_name).split(" ") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _serialize_user(uid: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": uid,
        "uid": uid,
        "uuid": _string(data.get("uuid")) or uid,
        "email": _string(data.get("email")),
        "first_name": _string(data.get("first_name")),
        "last_name": _string(data.get("last_name")),
        "display_name": _string(data.get("display_name")),
        "photo_url": _string(data.get("photo_url")),
        "created_at_iso": _string(data.get("created_at_iso")),
        "updated_at_iso": _string(data.get("updated_at_iso")),
        "fitness_profile": _serialize_profile(data.get("fitness_profile")),
    }


def ensure_user_profile(db, auth_user: dict[str, Any]) -> dict[str, Any]:
    uid = _string((auth_user or {}).get("uid"))
    if not uid:
        raise RuntimeError("Unable to resolve authenticated user.")

    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    snap = doc_ref.get()
    existing = snap.to_dict() or {}
    now_iso = _utc_now_iso()
    display_name = _string(auth_user.get("display_name")) or _string(existing.get("display_name"))
    first_name = _string(existing.get("first_name"))
    last_name = _string(existing.get("last_name"))
    if display_name and not (first_name or last_name):
        first_name, last_name = _split_display_name(display_name)

    base = {
        "uuid": uid,
        "uid": uid,
        "email": _string(auth_user.get("email")) or _string(existing.get("email")),
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "photo_url": _string(auth_user.get("picture")) or _string(existing.get("photo_url")),
        "fitness_profile": _serialize_profile(existing.get("fitness_profile")),
    }

    needs_write = not snap.exists
    payload = dict(base)
    if needs_write:
        payload["created_at"] = firestore.SERVER_TIMESTAMP
        payload["created_at_iso"] = now_iso
    payload["updated_at"] = firestore.SERVER_TIMESTAMP
    payload["updated_at_iso"] = now_iso
    if needs_write:
        doc_ref.set(payload, merge=True)

    merged = dict(existing)
    merged.update(payload if needs_write else base)
    return _serialize_user(uid, merged)


def _build_missing_fields(profile_data: dict[str, Any]) -> dict[str, list[str]]:
    height_missing: list[str] = []
    if profile_data.get("height_feet") is None:
        height_missing.append("height_feet")
    if profile_data.get("height_inches") is None:
        height_missing.append("height_inches")

    weight_missing = [] if profile_data.get("weight_lbs") is not None else ["weight_lbs"]
    bmi_missing = [*height_missing, *weight_missing]

    formula = profile_data.get("bmr_formula") or DEFAULT_BMR_FORMULA
    if formula == "katch_mcardle":
        bmr_missing = ["body_fat_percent"] if profile_data.get("body_fat_percent") is None else []
        bmr_missing.extend(weight_missing)
    else:
        bmr_missing = [*height_missing, *weight_missing]
        if profile_data.get("date_of_birth") is None:
            bmr_missing.append("date_of_birth")
        if not profile_data.get("sex_for_bmr"):
            bmr_missing.append("sex_for_bmr")

    activity_missing = [] if profile_data.get("activity_level") else ["activity_level"]
    tdee_missing = list(dict.fromkeys([*bmr_missing, *activity_missing]))
    return {
        "bmi": bmi_missing,
        "bmr": list(dict.fromkeys(bmr_missing)),
        "tdee": tdee_missing,
        "recommended_calories": list(tdee_missing),
    }


def _calculate_age(date_of_birth: date) -> int:
    today = _utc_now().date()
    years = today.year - date_of_birth.year
    before_birthday = (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    return years - (1 if before_birthday else 0)


def _height_inches_total(profile_data: dict[str, Any]) -> int | None:
    height_feet = profile_data.get("height_feet")
    height_inches = profile_data.get("height_inches")
    if height_feet is None or height_inches is None:
        return None
    return (int(height_feet) * 12) + int(height_inches)


def _bmi_category(bmi: float) -> tuple[str, str]:
    if bmi < 18.5:
        return "Underweight", "underweight"
    if bmi < 25:
        return "Healthy", "healthy"
    if bmi < 30:
        return "Overweight", "overweight"
    return "Obese", "obese"


def _bmi_position_pct(bmi: float) -> float:
    normalized = (bmi - BMI_VISUAL_MIN) / (BMI_VISUAL_MAX - BMI_VISUAL_MIN)
    return max(0.0, min(100.0, round(normalized * 100.0, 2)))


def _calculate_bmr(
    *,
    formula: str,
    weight_kg: float,
    height_cm: float,
    age_years: int | None,
    sex_for_bmr: str,
    body_fat_percent: float | None,
) -> int:
    if formula == "katch_mcardle":
        lean_mass_kg = weight_kg * (1.0 - ((body_fat_percent or 0.0) / 100.0))
        return int(round(370 + (21.6 * lean_mass_kg)))

    if age_years is None:
        raise ValueError("Age is required for the selected BMR formula.")

    if formula == "harris_benedict":
        if sex_for_bmr == "male":
            return int(round(88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age_years)))
        return int(round(447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age_years)))

    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years)
    return int(round(base + (5 if sex_for_bmr == "male" else -161)))


def _calculate_metrics(profile_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    missing_fields = _build_missing_fields(profile_data)
    metrics: dict[str, Any] = {
        "age_years": None,
        "bmi": None,
        "bmi_category": None,
        "bmi_zone": None,
        "bmi_position_pct": None,
        "bmr": None,
        "tdee": None,
        "activity_multiplier": None,
        "recommended_calories": {},
    }

    height_inches_total = _height_inches_total(profile_data)
    weight_lbs = profile_data.get("weight_lbs")
    weight_kg = (float(weight_lbs) * 0.45359237) if weight_lbs is not None else None

    if not missing_fields["bmi"] and height_inches_total and weight_kg is not None:
        height_m = float(height_inches_total) * 0.0254
        bmi = weight_kg / (height_m ** 2) if height_m > 0 else None
        if bmi is not None:
            category, zone = _bmi_category(bmi)
            metrics["bmi"] = round(bmi, 2)
            metrics["bmi_category"] = category
            metrics["bmi_zone"] = zone
            metrics["bmi_position_pct"] = _bmi_position_pct(bmi)

    formula = profile_data.get("bmr_formula") or DEFAULT_BMR_FORMULA
    if not missing_fields["bmr"]:
        if formula == "katch_mcardle":
            metrics["bmr"] = _calculate_bmr(
                formula=formula,
                weight_kg=float(weight_kg or 0),
                height_cm=0.0,
                age_years=None,
                sex_for_bmr="",
                body_fat_percent=float(profile_data.get("body_fat_percent") or 0),
            )
        else:
            date_of_birth = profile_data.get("date_of_birth")
            sex_for_bmr = profile_data.get("sex_for_bmr") or ""
            age_years = _calculate_age(date_of_birth)
            metrics["age_years"] = age_years
            height_cm = float(height_inches_total or 0) * 2.54
            metrics["bmr"] = _calculate_bmr(
                formula=formula,
                weight_kg=float(weight_kg or 0),
                height_cm=height_cm,
                age_years=age_years,
                sex_for_bmr=sex_for_bmr,
                body_fat_percent=None,
            )

    activity_level = profile_data.get("activity_level") or DEFAULT_ACTIVITY_LEVEL
    activity_multiplier = ACTIVITY_LEVEL_MAP.get(activity_level, ACTIVITY_LEVEL_MAP[DEFAULT_ACTIVITY_LEVEL])["multiplier"]
    metrics["activity_multiplier"] = activity_multiplier

    if not missing_fields["tdee"] and metrics["bmr"] is not None:
        metrics["tdee"] = int(round(float(metrics["bmr"]) * float(activity_multiplier)))

    if not missing_fields["recommended_calories"] and metrics["tdee"] is not None:
        recommended: dict[str, Any] = {}
        tdee = float(metrics["tdee"])
        for key, weekly_rate, label in CALORIE_TARGET_PRESETS:
            recommended[key] = {
                "label": label,
                "rate_lbs_per_week": weekly_rate,
                "calories": int(round(tdee + (weekly_rate * 500))),
            }
        custom_goal = profile_data.get("custom_goal_lbs_per_week")
        if custom_goal is not None:
            recommended["custom"] = {
                "label": "Custom",
                "rate_lbs_per_week": round(float(custom_goal), 2),
                "calories": int(round(tdee + (float(custom_goal) * 500))),
            }
        metrics["recommended_calories"] = recommended

    return metrics, missing_fields


def _coerce_payload(payload: dict[str, Any]) -> dict[str, Any]:
    first_name = _normalize_name(payload.get("first_name"))
    last_name = _normalize_name(payload.get("last_name"))

    date_of_birth = _parse_iso_date(payload.get("date_of_birth"))
    if _string(payload.get("date_of_birth")) and date_of_birth is None:
        raise ValueError("Enter a valid date of birth.")
    if date_of_birth and date_of_birth >= _utc_now().date():
        raise ValueError("Date of birth must be in the past.")

    height_feet = _parse_int(payload.get("height_feet"))
    height_inches = _parse_int(payload.get("height_inches"))
    if height_feet is None and height_inches is not None:
        raise ValueError("Enter both height fields.")
    if height_feet is not None and height_inches is None:
        raise ValueError("Enter both height fields.")
    if height_feet is not None and (height_feet < 1 or height_feet > 8):
        raise ValueError("Height in feet must be between 1 and 8.")
    if height_inches is not None and (height_inches < 0 or height_inches > 11):
        raise ValueError("Height inches must be between 0 and 11.")

    weight_lbs = _parse_float(payload.get("weight_lbs"))
    if _string(payload.get("weight_lbs")) and weight_lbs is None:
        raise ValueError("Enter a valid weight.")
    if weight_lbs is not None and weight_lbs <= 0:
        raise ValueError("Weight must be positive.")

    target_weight_lbs = _parse_float(payload.get("target_weight_lbs"))
    if _string(payload.get("target_weight_lbs")) and target_weight_lbs is None:
        raise ValueError("Enter a valid target weight.")
    if target_weight_lbs is not None and target_weight_lbs <= 0:
        raise ValueError("Target weight must be positive.")

    body_fat_percent = _parse_float(payload.get("body_fat_percent"))
    if _string(payload.get("body_fat_percent")) and body_fat_percent is None:
        raise ValueError("Enter a valid body-fat percentage.")
    if body_fat_percent is not None and (body_fat_percent <= 0 or body_fat_percent >= 100):
        raise ValueError("Body-fat percentage must be between 0 and 100.")

    custom_goal = _parse_float(payload.get("custom_goal_lbs_per_week"))
    if _string(payload.get("custom_goal_lbs_per_week")) and custom_goal is None:
        raise ValueError("Enter a valid custom weekly goal.")
    if custom_goal is not None and (custom_goal < CUSTOM_GOAL_MIN or custom_goal > CUSTOM_GOAL_MAX):
        raise ValueError("Custom goal must be between -2.0 and 2.0 lbs per week.")

    requested_bmr_formula = _string(payload.get("bmr_formula"))
    bmr_formula = _normalize_bmr_formula(payload.get("bmr_formula"))
    if requested_bmr_formula and bmr_formula == "katch_mcardle" and body_fat_percent is None:
        raise ValueError("Body-fat percentage is required for Katch-McArdle.")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
        "sex_for_bmr": _normalize_sex_for_bmr(payload.get("sex_for_bmr")),
        "height_feet": height_feet,
        "height_inches": height_inches,
        "weight_lbs": _round_or_none(weight_lbs),
        "target_weight_lbs": _round_or_none(target_weight_lbs),
        "activity_level": _normalize_activity_level(payload.get("activity_level")),
        "bmr_formula": bmr_formula,
        "body_fat_percent": _round_or_none(body_fat_percent),
        "custom_goal_lbs_per_week": _round_or_none(custom_goal),
    }


def _profile_response(user: dict[str, Any]) -> dict[str, Any]:
    profile_payload = _serialize_profile(user.get("fitness_profile"))
    metric_inputs = {
        **profile_payload,
        "date_of_birth": _parse_iso_date(profile_payload.get("date_of_birth")),
    }
    metrics, missing_fields = _calculate_metrics(metric_inputs)
    return {
        "user": {
            "uid": user["uid"],
            "uuid": user["uuid"],
            "display_name": user.get("display_name", ""),
            "email": user.get("email", ""),
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        },
        "profile": profile_payload,
        "metrics": metrics,
        "missing_fields": missing_fields,
        "activity_level_options": ACTIVITY_LEVEL_OPTIONS,
        "bmr_formula_options": BMR_FORMULA_OPTIONS,
    }


def build_fitness_profile_payload(db, *, auth_user: dict[str, Any]) -> dict[str, Any]:
    user = ensure_user_profile(db, auth_user)
    return _profile_response(user)


def save_fitness_profile_payload(
    db,
    *,
    auth_user: dict[str, Any],
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    uid = _string((auth_user or {}).get("uid"))
    if not uid:
        raise RuntimeError("Unable to resolve authenticated user.")

    cleaned = _coerce_payload(payload or {})
    now_iso = _utc_now_iso()
    doc_ref = db.collection(USERS_COLLECTION).document(uid)
    existing_snap = doc_ref.get()
    existing = existing_snap.to_dict() or {}
    existing_profile = _serialize_profile(existing.get("fitness_profile"))
    created_at_iso = existing_profile.get("created_at_iso") or now_iso
    next_profile = {
        **cleaned,
        "created_at_iso": created_at_iso,
        "updated_at_iso": now_iso,
    }
    first_name = cleaned["first_name"]
    last_name = cleaned["last_name"]
    display_name = " ".join(part for part in [first_name, last_name] if part).strip()
    updates = {
        "uuid": uid,
        "uid": uid,
        "email": _string(auth_user.get("email")) or _string(existing.get("email")),
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name or _string(auth_user.get("display_name")) or _string(existing.get("display_name")),
        "photo_url": _string(auth_user.get("picture")) or _string(existing.get("photo_url")),
        "fitness_profile": next_profile,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "updated_at_iso": now_iso,
    }
    if not existing_snap.exists:
        updates["created_at"] = firestore.SERVER_TIMESTAMP
        updates["created_at_iso"] = now_iso
    doc_ref.set(updates, merge=True)
    if cleaned["weight_lbs"] is not None:
        _upsert_weight_entry(
            db,
            uid=uid,
            payload={"date": _utc_now().date().isoformat(), "weight_lbs": cleaned["weight_lbs"], "source_unit": "lb"},
        )
        merged = doc_ref.get().to_dict() or {}
    else:
        merged = dict(existing)
        merged.update(updates)
    return _profile_response(_serialize_user(uid, merged))


def _lbs_to_kg(weight_lbs: float | None) -> float | None:
    if weight_lbs is None:
        return None
    return round(float(weight_lbs) * KG_PER_LB, 2)


def _kg_to_lbs(weight_kg: float | None) -> float | None:
    if weight_kg is None:
        return None
    return round(float(weight_kg) * LB_PER_KG, 2)


def _weight_collection(db, uid: str):
    return db.collection(USERS_COLLECTION).document(uid).collection(WEIGHT_ENTRIES_COLLECTION)


def _format_date_short(iso_date: str) -> str:
    parsed = _parse_iso_date(iso_date)
    if not parsed:
        return ""
    return parsed.strftime("%b %d").replace(" 0", " ")


def _resolve_weight_range(*, range_key: Any = None, start_date: Any = None, end_date: Any = None) -> dict[str, Any]:
    today = _utc_now().date()
    key = _string(range_key).lower() or "3m"
    raw_start = _string(start_date)
    raw_end = _string(end_date)
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if raw_start and start is None:
        raise ValueError("Enter a valid start date.")
    if raw_end and end is None:
        raise ValueError("Enter a valid end date.")
    if (start and start > today) or (end and end > today):
        raise ValueError("Weight history range cannot be in the future.")
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


def _coerce_weight_payload(payload: dict[str, Any] | None, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    existing = existing or {}
    parsed_date = _parse_iso_date(data.get("date")) or _parse_iso_date(existing.get("date")) or _utc_now().date()
    if _string(data.get("date")) and _parse_iso_date(data.get("date")) is None:
        raise ValueError("Enter a valid weight date.")
    if parsed_date > _utc_now().date():
        raise ValueError("Weight date cannot be in the future.")

    raw_lbs = _parse_float(data.get("weight_lbs"))
    raw_kg = _parse_float(data.get("weight_kg"))
    has_lbs = bool(_string(data.get("weight_lbs")))
    has_kg = bool(_string(data.get("weight_kg")))
    if has_kg:
        if raw_kg is None:
            raise ValueError("Enter a valid weight.")
        weight_lbs = _kg_to_lbs(raw_kg)
        source_unit = "kg"
    elif has_lbs:
        if raw_lbs is None:
            raise ValueError("Enter a valid weight.")
        weight_lbs = _round_or_none(raw_lbs)
        source_unit = "lb"
    else:
        weight_lbs = _round_or_none(_parse_float(existing.get("weight_lbs")))
        source_unit = _string(existing.get("source_unit")) or "lb"
    if weight_lbs is None:
        raise ValueError("Weight is required.")
    if weight_lbs <= 0:
        raise ValueError("Weight must be positive.")

    note = _string(data.get("note") if "note" in data else existing.get("note"))
    if len(note) > 500:
        note = note[:500].rstrip()

    return {
        "date": parsed_date.isoformat(),
        "weight_lbs": _round_or_none(weight_lbs),
        "source_unit": source_unit if source_unit in {"lb", "kg"} else "lb",
        "note": note,
    }


def _serialize_weight_entry(entry_id: str, data: dict[str, Any]) -> dict[str, Any]:
    date_iso = _parse_iso_date(data.get("date") or entry_id)
    weight_lbs = _round_or_none(_parse_float(data.get("weight_lbs")))
    return {
        "id": _string(entry_id),
        "date": date_iso.isoformat() if date_iso else _string(data.get("date") or entry_id),
        "date_label": _format_date_short(date_iso.isoformat()) if date_iso else "",
        "weight_lbs": weight_lbs,
        "weight_kg": _lbs_to_kg(weight_lbs),
        "source_unit": _string(data.get("source_unit")) or "lb",
        "note": _string(data.get("note")),
        "created_at_iso": _string(data.get("created_at_iso")),
        "updated_at_iso": _string(data.get("updated_at_iso")),
    }


def _list_weight_entries(db, *, uid: str) -> list[dict[str, Any]]:
    entries = []
    for snap in _weight_collection(db, uid).stream():
        data = snap.to_dict() or {}
        entry = _serialize_weight_entry(snap.id, data)
        if _parse_iso_date(entry.get("date")) and entry.get("weight_lbs") is not None:
            entries.append(entry)
    entries.sort(key=lambda item: _parse_iso_date(item.get("date")) or date.min)
    return entries


def _filter_entries_by_range(entries: list[dict[str, Any]], *, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
    filtered = []
    for entry in entries:
        parsed = _parse_iso_date(entry.get("date"))
        if not parsed:
            continue
        if start_date and parsed < start_date:
            continue
        if end_date and parsed > end_date:
            continue
        filtered.append(entry)
    return filtered


def _sync_profile_weight_to_latest(db, *, uid: str, entries: list[dict[str, Any]] | None = None) -> None:
    entries = entries if entries is not None else _list_weight_entries(db, uid=uid)
    if not entries:
        return
    latest = entries[-1]
    user_ref = db.collection(USERS_COLLECTION).document(uid)
    user_data = user_ref.get().to_dict() or {}
    profile = _serialize_profile(user_data.get("fitness_profile"))
    profile.update({
        "weight_lbs": latest.get("weight_lbs"),
        "weight_history_initialized": True,
        "updated_at_iso": _utc_now_iso(),
    })
    user_ref.set(
        {
            "fitness_profile": profile,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at_iso": profile["updated_at_iso"],
        },
        merge=True,
    )


def _ensure_weight_history_initialized(db, *, uid: str, profile: dict[str, Any]) -> None:
    profile_payload = _serialize_profile(profile)
    if profile_payload.get("weight_history_initialized"):
        return
    now_iso = _utc_now_iso()
    weight_lbs = profile_payload.get("weight_lbs")
    if weight_lbs is not None:
        today = _utc_now().date().isoformat()
        _weight_collection(db, uid).document(today).set(
            {
                "date": today,
                "weight_lbs": weight_lbs,
                "source_unit": "lb",
                "note": "",
                "created_at_iso": now_iso,
                "updated_at_iso": now_iso,
            },
            merge=True,
        )
    user_ref = db.collection(USERS_COLLECTION).document(uid)
    profile_payload["weight_history_initialized"] = True
    profile_payload["updated_at_iso"] = now_iso
    user_ref.set(
        {
            "fitness_profile": profile_payload,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at_iso": now_iso,
        },
        merge=True,
    )


def _upsert_weight_entry(db, *, uid: str, payload: dict[str, Any] | None, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    cleaned = _coerce_weight_payload(payload, existing=existing)
    now_iso = _utc_now_iso()
    entry_ref = _weight_collection(db, uid).document(cleaned["date"])
    current_snap = entry_ref.get()
    created_at_iso = _string((current_snap.to_dict() or {}).get("created_at_iso")) or _string((existing or {}).get("created_at_iso")) or now_iso
    entry = {
        **cleaned,
        "created_at_iso": created_at_iso,
        "updated_at_iso": now_iso,
    }
    entry_ref.set(entry, merge=True)
    _sync_profile_weight_to_latest(db, uid=uid)
    return _serialize_weight_entry(cleaned["date"], entry)


def _entry_metrics(profile_payload: dict[str, Any], weight_lbs: float | None) -> dict[str, Any]:
    metric_inputs = {
        **profile_payload,
        "weight_lbs": weight_lbs,
        "date_of_birth": _parse_iso_date(profile_payload.get("date_of_birth")),
    }
    metrics, _ = _calculate_metrics(metric_inputs)
    return metrics


def _entry_on_or_before(entries: list[dict[str, Any]], target_date: date) -> dict[str, Any] | None:
    candidates = [entry for entry in entries if (_parse_iso_date(entry.get("date")) or date.min) <= target_date]
    return candidates[-1] if candidates else None


def _build_weight_goal(profile_payload: dict[str, Any], latest_entry: dict[str, Any] | None) -> dict[str, Any]:
    target_lbs = profile_payload.get("target_weight_lbs")
    weekly_rate_lbs = profile_payload.get("custom_goal_lbs_per_week")
    latest_lbs = latest_entry.get("weight_lbs") if latest_entry else None
    delta_lbs = round(float(target_lbs) - float(latest_lbs), 2) if target_lbs is not None and latest_lbs is not None else None
    estimated_goal_date = None
    if delta_lbs is not None and weekly_rate_lbs not in (None, 0):
        rate = float(weekly_rate_lbs)
        if (delta_lbs > 0 and rate > 0) or (delta_lbs < 0 and rate < 0) or delta_lbs == 0:
            latest_date = _parse_iso_date(latest_entry.get("date")) if latest_entry else _utc_now().date()
            days = 0 if delta_lbs == 0 else int(round((abs(delta_lbs) / abs(rate)) * 7))
            estimated_goal_date = (latest_date + timedelta(days=max(0, days))).isoformat()
    return {
        "target_weight_lbs": target_lbs,
        "target_weight_kg": _lbs_to_kg(target_lbs),
        "weekly_rate_lbs": weekly_rate_lbs,
        "weekly_rate_kg": _lbs_to_kg(weekly_rate_lbs),
        "target_delta_lbs": delta_lbs,
        "target_delta_kg": _lbs_to_kg(delta_lbs),
        "estimated_goal_date": estimated_goal_date,
        "estimated_goal_date_label": _format_date_short(estimated_goal_date) if estimated_goal_date else None,
    }


def _build_weight_summary(entries: list[dict[str, Any]], filtered: list[dict[str, Any]], profile_payload: dict[str, Any]) -> dict[str, Any]:
    latest = entries[-1] if entries else None
    latest_metrics = _entry_metrics(profile_payload, latest.get("weight_lbs") if latest else profile_payload.get("weight_lbs"))
    range_change_lbs = None
    average_weekly_change_lbs = None
    if len(filtered) >= 2:
        first, last = filtered[0], filtered[-1]
        range_change_lbs = round(float(last["weight_lbs"]) - float(first["weight_lbs"]), 2)
        first_date = _parse_iso_date(first.get("date"))
        last_date = _parse_iso_date(last.get("date"))
        if first_date and last_date and last_date > first_date:
            average_weekly_change_lbs = round((range_change_lbs / max((last_date - first_date).days, 1)) * 7.0, 2)

    change_7d_lbs = None
    change_30d_lbs = None
    if latest:
        latest_date = _parse_iso_date(latest.get("date"))
        if latest_date:
            for days, key in [(7, "change_7d_lbs"), (30, "change_30d_lbs")]:
                previous = _entry_on_or_before(entries, latest_date - timedelta(days=days))
                if previous:
                    change = round(float(latest["weight_lbs"]) - float(previous["weight_lbs"]), 2)
                    if key == "change_7d_lbs":
                        change_7d_lbs = change
                    else:
                        change_30d_lbs = change

    goal = _build_weight_goal(profile_payload, latest)
    return {
        "latest_weight_lbs": latest.get("weight_lbs") if latest else profile_payload.get("weight_lbs"),
        "latest_weight_kg": _lbs_to_kg(latest.get("weight_lbs") if latest else profile_payload.get("weight_lbs")),
        "latest_date": latest.get("date") if latest else None,
        "latest_date_label": latest.get("date_label") if latest else None,
        "range_change_lbs": range_change_lbs,
        "range_change_kg": _lbs_to_kg(range_change_lbs),
        "change_7d_lbs": change_7d_lbs,
        "change_7d_kg": _lbs_to_kg(change_7d_lbs),
        "change_30d_lbs": change_30d_lbs,
        "change_30d_kg": _lbs_to_kg(change_30d_lbs),
        "average_weekly_change_lbs": average_weekly_change_lbs,
        "average_weekly_change_kg": _lbs_to_kg(average_weekly_change_lbs),
        "latest_bmi": latest_metrics.get("bmi"),
        "latest_bmi_category": latest_metrics.get("bmi_category"),
        "latest_bmi_zone": latest_metrics.get("bmi_zone"),
        "latest_bmr": latest_metrics.get("bmr"),
        "latest_tdee": latest_metrics.get("tdee"),
        "target_delta_lbs": goal.get("target_delta_lbs"),
        "target_delta_kg": goal.get("target_delta_kg"),
        "weekly_rate_lbs": goal.get("weekly_rate_lbs"),
        "weekly_rate_kg": goal.get("weekly_rate_kg"),
        "estimated_goal_date": goal.get("estimated_goal_date"),
        "estimated_goal_date_label": goal.get("estimated_goal_date_label"),
    }


def build_weight_history_payload(
    db,
    *,
    auth_user: dict[str, Any],
    range_key: Any = None,
    start_date: Any = None,
    end_date: Any = None,
) -> dict[str, Any]:
    user = ensure_user_profile(db, auth_user)
    uid = _string(user.get("uid"))
    _ensure_weight_history_initialized(db, uid=uid, profile=user.get("fitness_profile") or {})
    user = _serialize_user(uid, db.collection(USERS_COLLECTION).document(uid).get().to_dict() or {})
    profile_payload = _serialize_profile(user.get("fitness_profile"))
    all_entries = _list_weight_entries(db, uid=uid)
    range_payload = _resolve_weight_range(range_key=range_key, start_date=start_date, end_date=end_date)
    filtered = _filter_entries_by_range(
        all_entries,
        start_date=_parse_iso_date(range_payload.get("start_date")),
        end_date=_parse_iso_date(range_payload.get("end_date")),
    )
    chart_points = []
    for entry in filtered:
        metrics = _entry_metrics(profile_payload, entry.get("weight_lbs"))
        chart_points.append(
            {
                "date": entry["date"],
                "date_label": entry["date_label"],
                "weight_lbs": entry["weight_lbs"],
                "weight_kg": entry["weight_kg"],
                "bmi": metrics.get("bmi"),
                "bmr": metrics.get("bmr"),
                "tdee": metrics.get("tdee"),
            }
        )
    return {
        "user": {
            "uid": user["uid"],
            "uuid": user["uuid"],
            "display_name": user.get("display_name", ""),
            "email": user.get("email", ""),
        },
        "range": range_payload,
        "entries": list(reversed(filtered)),
        "summary": _build_weight_summary(all_entries, filtered, profile_payload),
        "chart_points": chart_points,
        "goal": _build_weight_goal(profile_payload, all_entries[-1] if all_entries else None),
    }


def create_weight_entry_payload(db, *, auth_user: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    user = ensure_user_profile(db, auth_user)
    uid = _string(user.get("uid"))
    entry = _upsert_weight_entry(db, uid=uid, payload=payload or {})
    return {
        "user": user,
        "entry": entry,
        "weight_history": build_weight_history_payload(db, auth_user=auth_user),
    }


def update_weight_entry_payload(db, *, auth_user: dict[str, Any], entry_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    user = ensure_user_profile(db, auth_user)
    uid = _string(user.get("uid"))
    current_ref = _weight_collection(db, uid).document(_string(entry_id))
    current_snap = current_ref.get()
    if not current_snap.exists:
        raise ValueError("Weight entry not found.")
    existing = _serialize_weight_entry(current_snap.id, current_snap.to_dict() or {})
    cleaned = _coerce_weight_payload(payload or {}, existing=existing)
    if cleaned["date"] != current_snap.id:
        next_ref = _weight_collection(db, uid).document(cleaned["date"])
        if next_ref.get().exists:
            raise ValueError("A weight entry already exists for that date.")
        current_ref.delete()
        entry = _upsert_weight_entry(db, uid=uid, payload=cleaned, existing=existing)
    else:
        entry = _upsert_weight_entry(db, uid=uid, payload=cleaned, existing=existing)
    return {
        "user": user,
        "entry": entry,
        "weight_history": build_weight_history_payload(db, auth_user=auth_user),
    }


def delete_weight_entry_payload(db, *, auth_user: dict[str, Any], entry_id: str) -> dict[str, Any]:
    user = ensure_user_profile(db, auth_user)
    uid = _string(user.get("uid"))
    ref = _weight_collection(db, uid).document(_string(entry_id))
    snap = ref.get()
    if not snap.exists:
        raise ValueError("Weight entry not found.")
    ref.delete()
    _sync_profile_weight_to_latest(db, uid=uid)
    return {
        "user": user,
        "deleted": True,
        "entry_id": _string(entry_id),
        "weight_history": build_weight_history_payload(db, auth_user=auth_user),
    }
