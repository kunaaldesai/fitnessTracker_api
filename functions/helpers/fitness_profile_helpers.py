from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from firebase_admin import firestore

USERS_COLLECTION = "users"

DEFAULT_BMR_FORMULA = "katch_mcardle"
DEFAULT_ACTIVITY_LEVEL = "sedentary"
BMI_VISUAL_MIN = 15.0
BMI_VISUAL_MAX = 40.0
CUSTOM_GOAL_MIN = -2.0
CUSTOM_GOAL_MAX = 2.0

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
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        return float(raw)
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
        "activity_level": DEFAULT_ACTIVITY_LEVEL,
        "bmr_formula": DEFAULT_BMR_FORMULA,
        "body_fat_percent": None,
        "custom_goal_lbs_per_week": None,
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
    profile["body_fat_percent"] = _round_or_none(_parse_float(profile.get("body_fat_percent")))
    profile["custom_goal_lbs_per_week"] = _round_or_none(_parse_float(profile.get("custom_goal_lbs_per_week")))
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
    merged = dict(existing)
    merged.update(updates)
    return _profile_response(_serialize_user(uid, merged))
