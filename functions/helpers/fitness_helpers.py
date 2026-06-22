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

USERS_COLLECTION = "users"
WORKOUT_DAYS_COLLECTION = "workout_days"
EXERCISE_ENTRIES_COLLECTION = "exercise_entries"
EXERCISE_DEFINITIONS_COLLECTION = "exercise_definitions"
EXERCISE_RECORDS_COLLECTION = "exercise_records"
EXERCISE_CATALOG_COLLECTION = "exercise_catalog"
FITNESS_EXERCISES_COLLECTION = "fitness_exercises"
FIRESTORE_SCHEMA_VERSION = 2
_WRITE_BATCH_LIMIT = 400
MAX_CALENDAR_DAYS = 731
MAX_SETS_PER_EXERCISE = 40
MAX_COPY_EXERCISES = 75
MAX_EXERCISE_WEIGHT_LBS = 2000.0
MAX_EXERCISE_REPS = 1000
MAX_EXERCISE_DURATION_SECONDS = 24 * 60 * 60
MAX_EXERCISE_DISTANCE_MILES = 1000.0

CATEGORY_OPTIONS = [
    "Chest",
    "Back",
    "Shoulders",
    "Traps",
    "Biceps",
    "Triceps",
    "Forearms",
    "Abs",
    "Adductors",
    "Quads",
    "Hamstrings",
    "Glutes",
    "Calves",
    "Cardio",
]

TYPE_OPTIONS = ["Strength", "Cardio", "Stretching"]

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
    "trap": "Traps",
    "traps": "Traps",
    "forearm": "Forearms",
    "forearms": "Forearms",
    "ab": "Abs",
    "abs": "Abs",
    "core": "Abs",
    "adductor": "Adductors",
    "adductors": "Adductors",
    "inner thigh": "Adductors",
    "glute": "Glutes",
    "glutes": "Glutes",
    "calf": "Calves",
    "calves": "Calves",
    "cardio": "Cardio",
    "conditioning": "Cardio",
}

TYPE_ALIAS_MAP = {
    "strength": "Strength",
    "compound": "Strength",
    "isolation": "Strength",
    "cardio": "Cardio",
    "conditioning": "Cardio",
    "stretch": "Stretching",
    "stretching": "Stretching",
    "mobility": "Stretching",
    "yoga": "Stretching",
}

DEFAULT_EXERCISE_LIBRARY: list[dict[str, str]] = [
    {"name": "Ab Wheel Rollout", "category": "Abs", "movement_type": "Strength"},
    {"name": "Alternating Dumbbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Arnold Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Assisted Dip", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Assisted Pull Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Back Extension", "category": "Back", "movement_type": "Strength"},
    {"name": "Barbell Back Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Barbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Barbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Barbell Glute Bridge", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Barbell Hip Thrust", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Barbell Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Barbell Shrug", "category": "Traps", "movement_type": "Strength"},
    {"name": "Bayesian Cable Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Behind Back Wrist Curl", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Bench Dip", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Banded Lateral Walk", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Bicycle Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Bulgarian Split Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Cable Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Cable Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Cable Fly", "category": "Chest", "movement_type": "Strength"},
    {"name": "Cable Hip Abduction", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Cable Hip Adduction", "category": "Adductors", "movement_type": "Strength"},
    {"name": "Cable Lateral Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Cable Pull Through", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Cable Y Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Captain's Chair Knee Raise", "category": "Abs", "movement_type": "Strength"},
    {"name": "Chest Dip", "category": "Chest", "movement_type": "Strength"},
    {"name": "Chest Supported Dumbbell Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Chest Supported Machine Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Chin Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Clamshell", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Close Grip Bench Press", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Close Grip Lat Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Concentration Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Conventional Deadlift", "category": "Back", "movement_type": "Strength"},
    {"name": "Copenhagen Plank", "category": "Adductors", "movement_type": "Strength"},
    {"name": "Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Dead Bug", "category": "Abs", "movement_type": "Strength"},
    {"name": "Dead Hang", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Decline Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Deficit Push Up", "category": "Chest", "movement_type": "Strength"},
    {"name": "Diamond Push Up", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Donkey Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Dumbbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Dumbbell Fly", "category": "Chest", "movement_type": "Strength"},
    {"name": "Dumbbell Glute Bridge", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Dumbbell Pullover", "category": "Chest", "movement_type": "Strength"},
    {"name": "Dumbbell Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Dumbbell Shoulder Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Dumbbell Shrug", "category": "Traps", "movement_type": "Strength"},
    {"name": "Dumbbell Y Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "EZ Bar Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "EZ Bar Skull Crusher", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Face Pull", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Farmer Carry", "category": "Traps", "movement_type": "Strength"},
    {"name": "Flat Dumbbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Floor Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Forward Lunge", "category": "Quads", "movement_type": "Strength"},
    {"name": "Front Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Front Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Frog Pump", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Glute Ham Raise", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Goblet Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Good Morning", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Gripper Squeeze", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Hack Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Hammer Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Hanging Knee Raise", "category": "Abs", "movement_type": "Strength"},
    {"name": "Hanging Leg Raise", "category": "Abs", "movement_type": "Strength"},
    {"name": "Heavy Farmer Carry", "category": "Forearms", "movement_type": "Strength"},
    {"name": "High Bar Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Hip Abduction Machine", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Hip Adduction Machine", "category": "Adductors", "movement_type": "Strength"},
    {"name": "Hip Thrust", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Hollow Body Hold", "category": "Abs", "movement_type": "Strength"},
    {"name": "Incline Barbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Incline Dumbbell Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Incline Dumbbell Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Incline Push Up", "category": "Chest", "movement_type": "Strength"},
    {"name": "Inverted Row", "category": "Back", "movement_type": "Strength"},
    {"name": "JM Press", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Landmine Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Lateral Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Lat Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Lean Back Cable Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Leaning Cable Lateral Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Leg Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Leg Extension", "category": "Quads", "movement_type": "Strength"},
    {"name": "Leg Press", "category": "Quads", "movement_type": "Strength"},
    {"name": "Leg Press Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Low Bar Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Low Cable Fly", "category": "Chest", "movement_type": "Strength"},
    {"name": "Lying Leg Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Machine Chest Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Machine Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Machine Glute Kickback", "category": "Glutes", "movement_type": "Strength"},
    {"name": "Machine Hack Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Machine Preacher Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Machine Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Machine Shoulder Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Machine Shrug", "category": "Traps", "movement_type": "Strength"},
    {"name": "Meadows Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Mountain Climber", "category": "Abs", "movement_type": "Strength"},
    {"name": "Neutral Grip Pull Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Nordic Hamstring Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Overhead Cable Tricep Extension", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Overhead Dumbbell Tricep Extension", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Overhead Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Pallof Press", "category": "Abs", "movement_type": "Strength"},
    {"name": "Pec Deck", "category": "Chest", "movement_type": "Strength"},
    {"name": "Pendlay Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Pistol Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Plate Front Raise", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Plate Pinch", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Plank", "category": "Abs", "movement_type": "Strength"},
    {"name": "Preacher Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Pronation Supination", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Pull Up", "category": "Back", "movement_type": "Strength"},
    {"name": "Push Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Push Up", "category": "Chest", "movement_type": "Strength"},
    {"name": "Rack Pull", "category": "Back", "movement_type": "Strength"},
    {"name": "Rear Delt Fly", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Reverse Crunch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Reverse Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Reverse Lunge", "category": "Quads", "movement_type": "Strength"},
    {"name": "Reverse Pec Deck", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Reverse Wrist Curl", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Romanian Deadlift", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Rope Tricep Pushdown", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Russian Twist", "category": "Abs", "movement_type": "Strength"},
    {"name": "Seated Barbell Shoulder Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Seated Cable Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Seated Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Seated Dumbbell Shoulder Press", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "Seated Leg Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Side Plank", "category": "Abs", "movement_type": "Strength"},
    {"name": "Single Arm Cable Tricep Extension", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Single Arm Lat Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Single Leg Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Single Leg Press", "category": "Quads", "movement_type": "Strength"},
    {"name": "Single Leg Romanian Deadlift", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Sit Up", "category": "Abs", "movement_type": "Strength"},
    {"name": "Sissy Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Skull Crusher", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Slider Leg Curl", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Smith Machine Bench Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "Smith Machine Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Smith Machine Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Spider Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Split Squat", "category": "Quads", "movement_type": "Strength"},
    {"name": "Standing Calf Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Step Up", "category": "Quads", "movement_type": "Strength"},
    {"name": "Stiff Leg Deadlift", "category": "Hamstrings", "movement_type": "Strength"},
    {"name": "Straight Arm Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Suitcase Carry", "category": "Traps", "movement_type": "Strength"},
    {"name": "Sumo Deadlift", "category": "Back", "movement_type": "Strength"},
    {"name": "Sumo Squat", "category": "Adductors", "movement_type": "Strength"},
    {"name": "Superman", "category": "Back", "movement_type": "Strength"},
    {"name": "Svend Press", "category": "Chest", "movement_type": "Strength"},
    {"name": "T-Bar Row", "category": "Back", "movement_type": "Strength"},
    {"name": "Tibialis Raise", "category": "Calves", "movement_type": "Strength"},
    {"name": "Toe Touch", "category": "Abs", "movement_type": "Strength"},
    {"name": "Trap Bar Shrug", "category": "Traps", "movement_type": "Strength"},
    {"name": "Tricep Kickback", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Tricep Pushdown", "category": "Triceps", "movement_type": "Strength"},
    {"name": "Towel Hang", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Upright Row", "category": "Shoulders", "movement_type": "Strength"},
    {"name": "V Up", "category": "Abs", "movement_type": "Strength"},
    {"name": "Wall Sit", "category": "Quads", "movement_type": "Strength"},
    {"name": "Weighted Dip", "category": "Chest", "movement_type": "Strength"},
    {"name": "Wide Grip Lat Pulldown", "category": "Back", "movement_type": "Strength"},
    {"name": "Wood Chop", "category": "Abs", "movement_type": "Strength"},
    {"name": "Wrist Curl", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Wrist Roller", "category": "Forearms", "movement_type": "Strength"},
    {"name": "Zottman Curl", "category": "Biceps", "movement_type": "Strength"},
    {"name": "Agility Ladder", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Assault Bike", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Battle Ropes", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Boxing", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Burpee", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Dance Cardio", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Elliptical", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Heavy Bag", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "High Knees", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Hiking", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Incline Treadmill Walk", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Interval Run", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Jump Rope", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Jumping Jacks", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Kickboxing", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Lap Swim", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Outdoor Cycling", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Outdoor Run", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Outdoor Walk", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Recumbent Bike", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Rowing Machine", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Shadow Boxing", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "SkiErg", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Sled Pull", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Sled Push", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Spin Bike", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Stair Climber", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Stairmaster", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Stationary Bike", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "StepMill", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Swimming", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Trail Run", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Treadmill Run", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Treadmill Walk", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Water Jogging", "category": "Cardio", "movement_type": "Cardio"},
    {"name": "Achilles Stretch", "category": "Calves", "movement_type": "Stretching"},
    {"name": "Biceps Wall Stretch", "category": "Biceps", "movement_type": "Stretching"},
    {"name": "Butterfly Stretch", "category": "Adductors", "movement_type": "Stretching"},
    {"name": "Calf Stretch", "category": "Calves", "movement_type": "Stretching"},
    {"name": "Cat Cow", "category": "Back", "movement_type": "Stretching"},
    {"name": "Chest Stretch", "category": "Chest", "movement_type": "Stretching"},
    {"name": "Child's Pose", "category": "Back", "movement_type": "Stretching"},
    {"name": "Cobra Stretch", "category": "Abs", "movement_type": "Stretching"},
    {"name": "Cossack Squat Stretch", "category": "Adductors", "movement_type": "Stretching"},
    {"name": "Couch Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "Cross Body Shoulder Stretch", "category": "Shoulders", "movement_type": "Stretching"},
    {"name": "Cross Body Tricep Stretch", "category": "Triceps", "movement_type": "Stretching"},
    {"name": "Doorway Pec Stretch", "category": "Chest", "movement_type": "Stretching"},
    {"name": "Doorway Shoulder Stretch", "category": "Shoulders", "movement_type": "Stretching"},
    {"name": "Downward Dog", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Downward Dog Calf Pedal", "category": "Calves", "movement_type": "Stretching"},
    {"name": "Figure Four Stretch", "category": "Glutes", "movement_type": "Stretching"},
    {"name": "Frog Stretch", "category": "Adductors", "movement_type": "Stretching"},
    {"name": "Hamstring Stretch", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Hip Flexor Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "Knee to Chest Stretch", "category": "Glutes", "movement_type": "Stretching"},
    {"name": "Kneeling Quad Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "Lat Stretch", "category": "Back", "movement_type": "Stretching"},
    {"name": "Levator Scapulae Stretch", "category": "Traps", "movement_type": "Stretching"},
    {"name": "Lizard Pose", "category": "Glutes", "movement_type": "Stretching"},
    {"name": "Low Lunge Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "Overhead Tricep Stretch", "category": "Triceps", "movement_type": "Stretching"},
    {"name": "Pigeon Pose", "category": "Glutes", "movement_type": "Stretching"},
    {"name": "Prayer Stretch", "category": "Forearms", "movement_type": "Stretching"},
    {"name": "Seated Forward Fold", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Seated Hamstring Stretch", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Seated Piriformis Stretch", "category": "Glutes", "movement_type": "Stretching"},
    {"name": "Seated Straddle Stretch", "category": "Adductors", "movement_type": "Stretching"},
    {"name": "Side Lunge Stretch", "category": "Adductors", "movement_type": "Stretching"},
    {"name": "Single Leg Forward Fold", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Sleeper Stretch", "category": "Shoulders", "movement_type": "Stretching"},
    {"name": "Soleus Stretch", "category": "Calves", "movement_type": "Stretching"},
    {"name": "Sphinx Pose", "category": "Abs", "movement_type": "Stretching"},
    {"name": "Standing Hamstring Stretch", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Standing Quad Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "Supine Hamstring Stretch", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Thread the Needle", "category": "Back", "movement_type": "Stretching"},
    {"name": "Toe Touch Stretch", "category": "Hamstrings", "movement_type": "Stretching"},
    {"name": "Upper Trap Stretch", "category": "Traps", "movement_type": "Stretching"},
    {"name": "Upward Dog", "category": "Abs", "movement_type": "Stretching"},
    {"name": "Wall Calf Stretch", "category": "Calves", "movement_type": "Stretching"},
    {"name": "Wall Chest Stretch", "category": "Chest", "movement_type": "Stretching"},
    {"name": "Wrist Extensor Stretch", "category": "Forearms", "movement_type": "Stretching"},
    {"name": "Wrist Flexor Stretch", "category": "Forearms", "movement_type": "Stretching"},
    {"name": "World's Greatest Stretch", "category": "Quads", "movement_type": "Stretching"},
    {"name": "90/90 Hip Stretch", "category": "Glutes", "movement_type": "Stretching"},
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


def _doc_key(value: Any) -> str:
    key = " ".join(_exercise_key(value).replace("/", " ").split())
    return key[:180] or "unknown"


def _category_key(value: Any) -> str:
    return _doc_key(_normalize_category(value))


def _movement_type_key(value: Any) -> str:
    return _doc_key(_normalize_movement_type(value))


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


def _movement_key(value: Any) -> str:
    return _normalize_movement_type(value).casefold() or "strength"


def _is_strength_movement(value: Any) -> bool:
    return _movement_key(value) == "strength"


def _is_cardio_movement(value: Any) -> bool:
    return _movement_key(value) == "cardio"


def _is_stretching_movement(value: Any) -> bool:
    return _movement_key(value) == "stretching"


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
        duration_seconds = _safe_float(raw_set.get("duration_seconds"))
        if duration_seconds is None and _safe_float(raw_set.get("duration_minutes")) is not None:
            duration_seconds = (_safe_float(raw_set.get("duration_minutes")) or 0.0) * 60.0
        if validate and duration_seconds is not None and duration_seconds > MAX_EXERCISE_DURATION_SECONDS:
            raise ValueError("Set duration must be at most 24 hours.")
        distance_miles = _safe_float(raw_set.get("distance_miles"))
        if validate and distance_miles is not None and distance_miles > MAX_EXERCISE_DISTANCE_MILES:
            raise ValueError(f"Set distance must be at most {MAX_EXERCISE_DISTANCE_MILES:g} miles.")
        normalized.append(
            {
                "weight": min(weight, MAX_EXERCISE_WEIGHT_LBS) if weight is not None else None,
                "reps": min(reps, MAX_EXERCISE_REPS) if reps is not None else None,
                "rpe": rpe,
                "duration_seconds": min(duration_seconds, MAX_EXERCISE_DURATION_SECONDS) if duration_seconds is not None else None,
                "distance_miles": min(distance_miles, MAX_EXERCISE_DISTANCE_MILES) if distance_miles is not None else None,
                "side": _normalize_text(raw_set.get("side"), max_len=40),
            }
        )
    return normalized or [{"weight": None, "reps": None, "rpe": None, "duration_seconds": None, "distance_miles": None, "side": ""}]


def _set_volume(weight: float | None, reps: int | None) -> float:
    if weight is None or reps is None:
        return 0.0
    return max(0.0, float(weight) * int(reps))


def _set_calculated_one_rm(weight: float | None, reps: int | None) -> float:
    if weight is None or reps is None or weight <= 0 or reps <= 0:
        return 0.0
    return max(0.0, float(weight) * (1.0 + (float(reps) / 30.0)))


def _set_duration_seconds(set_row: dict[str, Any]) -> float:
    return _safe_float(set_row.get("duration_seconds")) or 0.0


def _set_distance_miles(set_row: dict[str, Any]) -> float:
    return _safe_float(set_row.get("distance_miles")) or 0.0


def _set_is_complete(set_row: dict[str, Any], movement_type: Any) -> bool:
    if _is_strength_movement(movement_type):
        return _set_volume(_safe_float(set_row.get("weight")), _safe_int(set_row.get("reps"))) > 0
    if _is_cardio_movement(movement_type):
        return _set_duration_seconds(set_row) > 0 or _set_distance_miles(set_row) > 0
    if _is_stretching_movement(movement_type):
        return _set_duration_seconds(set_row) > 0
    return (
        _set_volume(_safe_float(set_row.get("weight")), _safe_int(set_row.get("reps"))) > 0
        or _set_duration_seconds(set_row) > 0
        or _set_distance_miles(set_row) > 0
    )


def _serialize_exercise(exercise_id: str, data: dict[str, Any]) -> dict[str, Any]:
    serialized_sets: list[dict[str, Any]] = []
    total_volume = 0.0
    total_duration_seconds = 0.0
    total_distance_miles = 0.0
    completed_sets = 0
    name = _normalize_text(data.get("name"), max_len=160)
    category, movement_type = _coalesce_exercise_metadata(
        name=name,
        category=data.get("category"),
        movement_type=data.get("movement_type"),
    )
    for index, item in enumerate(_normalize_sets(data.get("sets"))):
        weight = _safe_float(item.get("weight"))
        reps = _safe_int(item.get("reps"))
        rpe = _safe_float(item.get("rpe"))
        if rpe is not None:
            rpe = max(0.0, min(10.0, rpe))
        duration_seconds = _set_duration_seconds(item)
        distance_miles = _set_distance_miles(item)
        volume = _set_volume(weight, reps) if _is_strength_movement(movement_type) else 0.0
        if _set_is_complete(item, movement_type):
            completed_sets += 1
        total_volume += volume
        total_duration_seconds += duration_seconds
        total_distance_miles += distance_miles
        serialized_sets.append(
            {
                "set_number": index + 1,
                "weight": weight,
                "reps": reps,
                "rpe": rpe,
                "duration_seconds": round(duration_seconds, 2) if duration_seconds > 0 else None,
                "distance_miles": round(distance_miles, 3) if distance_miles > 0 else None,
                "side": _normalize_text(item.get("side"), max_len=40),
                "volume": round(volume, 2),
                "one_rm": round(_set_calculated_one_rm(weight, reps), 2),
            }
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
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_distance_miles": round(total_distance_miles, 3),
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


def _user_ref(db, owner_uuid: str):
    return db.collection(USERS_COLLECTION).document(owner_uuid)


def _workout_days_collection(db, owner_uuid: str):
    return _user_ref(db, owner_uuid).collection(WORKOUT_DAYS_COLLECTION)


def _workout_day_ref(db, owner_uuid: str, workout_date_iso: str):
    return _workout_days_collection(db, owner_uuid).document(workout_date_iso)


def _exercise_entries_collection(db, owner_uuid: str, workout_date_iso: str):
    return _workout_day_ref(db, owner_uuid, workout_date_iso).collection(EXERCISE_ENTRIES_COLLECTION)


def _exercise_entry_ref(db, owner_uuid: str, workout_date_iso: str, exercise_id: str):
    return _exercise_entries_collection(db, owner_uuid, workout_date_iso).document(exercise_id)


def _exercise_definitions_collection(db, owner_uuid: str):
    return _user_ref(db, owner_uuid).collection(EXERCISE_DEFINITIONS_COLLECTION)


def _exercise_records_collection(db, owner_uuid: str):
    return _user_ref(db, owner_uuid).collection(EXERCISE_RECORDS_COLLECTION)


def _exercise_entries_group(db):
    if not hasattr(db, "collection_group"):
        raise RuntimeError("Firestore collection group queries are not configured.")
    return db.collection_group(EXERCISE_ENTRIES_COLLECTION)


def _entry_storage_doc(
    *,
    owner_uuid: str,
    exercise_id: str,
    workout_date_iso: str,
    order_index: int,
    name: str,
    category: Any,
    movement_type: Any,
    notes: Any,
    sets: Any,
    created_at_iso: str,
    updated_at_iso: str,
    timezone_name: Any = None,
    validate_sets: bool = False,
) -> dict[str, Any]:
    normalized_category, normalized_type = _coalesce_exercise_metadata(
        name=name,
        category=category,
        movement_type=movement_type,
    )
    normalized_sets = _normalize_sets(sets, validate=validate_sets)
    base = {
        "owner_uuid": owner_uuid,
        "uid": owner_uuid,
        "entry_id": exercise_id,
        "workout_date": workout_date_iso,
        "day_id": workout_date_iso,
        "order_index": order_index,
        "name": name,
        "name_key": _doc_key(name),
        "category": normalized_category,
        "category_key": _category_key(normalized_category),
        "movement_type": normalized_type,
        "movement_type_key": _movement_type_key(normalized_type),
        "type": normalized_type,
        "notes": _normalize_notes(notes, max_len=5000),
        "sets": normalized_sets,
        "timezone": _normalize_text(timezone_name, max_len=80) or "UTC",
        "schema_version": FIRESTORE_SCHEMA_VERSION,
        "created_at_iso": created_at_iso,
        "updated_at_iso": updated_at_iso,
    }
    serialized = _serialize_exercise(exercise_id, base)
    base.update(
        {
            "total_volume": serialized["total_volume"],
            "total_duration_seconds": serialized["total_duration_seconds"],
            "total_distance_miles": serialized["total_distance_miles"],
            "completed_sets": serialized["completed_sets"],
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return base


def _serialize_entry_snapshot(snap) -> dict[str, Any]:
    data = snap.to_dict() or {}
    return _serialize_exercise(_string(data.get("entry_id")) or snap.id, data)


def _list_owner_exercises_for_name(db, *, owner_uuid: str, name_key: str) -> list[dict[str, Any]]:
    query = _where_eq(_exercise_entries_group(db), "uid", owner_uuid)
    query = _where_eq(query, "name_key", _doc_key(name_key))
    exercises = [_serialize_entry_snapshot(snap) for snap in query.stream()]
    exercises.sort(
        key=lambda item: (
            _string(item.get("workout_date")),
            _safe_order(item.get("order_index")),
            _string(item.get("id")),
        )
    )
    return exercises


def _exercise_snapshot_for_owner(db, *, owner_uuid: str, exercise_id: str):
    query = _where_eq(_exercise_entries_group(db), "uid", owner_uuid)
    query = _where_eq(query, "entry_id", _string(exercise_id))
    for snap in query.stream():
        payload = snap.to_dict() or {}
        if _string(payload.get("uid")) == owner_uuid:
            return snap
    raise ValueError("Exercise not found.")


def list_day_exercises(db, *, owner_uuid: str, workout_date_iso: str) -> list[dict[str, Any]]:
    exercises = [
        _serialize_entry_snapshot(snap)
        for snap in _exercise_entries_collection(db, owner_uuid, workout_date_iso).stream()
    ]
    exercises.sort(key=lambda item: (_safe_order(item.get("order_index")), _string(item.get("id"))))
    return exercises


def _list_owner_exercises_for_workout_days(db, *, owner_uuid: str, workout_days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exercises: list[dict[str, Any]] = []
    for day_row in workout_days:
        workout_date_iso = _string(day_row.get("date")) or _string(day_row.get("id"))
        if _parse_iso_date(workout_date_iso) is None:
            continue
        exercises.extend(list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso))
    exercises.sort(
        key=lambda item: (
            _string(item.get("workout_date")),
            _safe_order(item.get("order_index")),
            _string(item.get("id")),
        )
    )
    return exercises


def _list_all_owner_exercises(db, *, owner_uuid: str) -> list[dict[str, Any]]:
    return _list_owner_exercises_for_workout_days(
        db,
        owner_uuid=owner_uuid,
        workout_days=_list_owner_workout_days(db, owner_uuid=owner_uuid),
    )


def _list_owner_workout_days(db, *, owner_uuid: str) -> list[dict[str, Any]]:
    rows = []
    for snap in _workout_days_collection(db, owner_uuid).stream():
        data = snap.to_dict() or {}
        date_iso = _string(data.get("date")) or snap.id
        if _parse_iso_date(date_iso):
            rows.append({"id": snap.id, **data, "date": date_iso})
    rows.sort(key=lambda item: _parse_iso_date(item.get("date")) or date.min)
    return rows


def _next_order_index(db, *, owner_uuid: str, workout_date_iso: str) -> int:
    day_snap = _workout_day_ref(db, owner_uuid, workout_date_iso).get()
    stored_next = _safe_order((day_snap.to_dict() or {}).get("next_order_index")) if day_snap.exists else 0
    max_order = -1
    for exercise in list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso):
        max_order = max(max_order, _safe_order(exercise.get("order_index")))
    return max(stored_next, max_order + 1)


def _day_rollup_from_exercises(exercises: list[dict[str, Any]]) -> dict[str, Any]:
    category_summaries: dict[str, dict[str, Any]] = {}
    movement_type_summaries: dict[str, dict[str, Any]] = {}
    total_volume = 0.0
    total_duration_seconds = 0.0
    total_distance_miles = 0.0
    sets_completed = 0
    for exercise in exercises:
        category = _normalize_category(exercise.get("category")) or "Other"
        movement_type = _normalize_movement_type(exercise.get("movement_type")) or "Strength"
        completed_sets = int(exercise.get("completed_sets") or 0)
        volume = float(exercise.get("total_volume") or 0)
        duration = float(exercise.get("total_duration_seconds") or 0)
        distance = float(exercise.get("total_distance_miles") or 0)
        total_volume += volume
        total_duration_seconds += duration
        total_distance_miles += distance
        sets_completed += completed_sets
        for bucket_key, summaries in [(category, category_summaries), (movement_type, movement_type_summaries)]:
            bucket = summaries.setdefault(
                bucket_key,
                {
                    "exercise_count": 0,
                    "completed_sets": 0,
                    "total_volume": 0.0,
                    "total_duration_seconds": 0.0,
                    "total_distance_miles": 0.0,
                },
            )
            bucket["exercise_count"] += 1
            bucket["completed_sets"] += completed_sets
            bucket["total_volume"] = round(float(bucket["total_volume"]) + volume, 2)
            bucket["total_duration_seconds"] = round(float(bucket["total_duration_seconds"]) + duration, 2)
            bucket["total_distance_miles"] = round(float(bucket["total_distance_miles"]) + distance, 3)
    return {
        "exercise_count": len(exercises),
        "sets_completed": sets_completed,
        "total_volume": round(total_volume, 2),
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_distance_miles": round(total_distance_miles, 3),
        "category_summaries": category_summaries,
        "movement_type_summaries": movement_type_summaries,
        "category_counts": {key: int(value.get("exercise_count") or 0) for key, value in category_summaries.items()},
        "type_counts": {key: int(value.get("exercise_count") or 0) for key, value in movement_type_summaries.items()},
    }


def _recompute_workout_day(db, *, owner_uuid: str, workout_date_iso: str) -> None:
    day_ref = _workout_day_ref(db, owner_uuid, workout_date_iso)
    existing_snap = day_ref.get()
    existing = existing_snap.to_dict() or {}
    exercises = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)
    if not exercises:
        if existing_snap.exists:
            day_ref.delete()
        return
    now_iso = _utc_now_iso()
    rollup = _day_rollup_from_exercises(exercises)
    max_order = max((_safe_order(exercise.get("order_index")) for exercise in exercises), default=-1)
    timezone_name = _normalize_text(existing.get("timezone"), max_len=80) or _normalize_text(exercises[0].get("timezone"), max_len=80) or "UTC"
    doc = {
        "uid": owner_uuid,
        "owner_uuid": owner_uuid,
        "date": workout_date_iso,
        "day_id": workout_date_iso,
        "timezone": timezone_name,
        "schema_version": FIRESTORE_SCHEMA_VERSION,
        "next_order_index": max_order + 1,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "updated_at_iso": now_iso,
        **rollup,
    }
    if not existing_snap.exists:
        doc["created_at"] = firestore.SERVER_TIMESTAMP
        doc["created_at_iso"] = now_iso
    else:
        doc["created_at_iso"] = _string(existing.get("created_at_iso")) or now_iso
    day_ref.set(doc, merge=True)


def _sync_user_exercise_definition(db, *, owner_uuid: str, name_key: str) -> None:
    normalized_key = _doc_key(name_key)
    exercises = _list_owner_exercises_for_name(db, owner_uuid=owner_uuid, name_key=normalized_key)
    definition_ref = _exercise_definitions_collection(db, owner_uuid).document(normalized_key)
    if not exercises:
        definition_ref.delete()
        return
    latest = max(exercises, key=lambda item: (_string(item.get("updated_at_iso")), _string(item.get("workout_date"))))
    name = _normalize_text(latest.get("name"), max_len=160)
    category, movement_type = _coalesce_exercise_metadata(
        name=name,
        category=latest.get("category"),
        movement_type=latest.get("movement_type"),
    )
    now_iso = _utc_now_iso()
    definition_ref.set(
        {
            "uid": owner_uuid,
            "name": name,
            "name_key": normalized_key,
            "category": category,
            "category_key": _category_key(category),
            "movement_type": movement_type,
            "movement_type_key": _movement_type_key(movement_type),
            "type": movement_type,
            "source": "custom",
            "session_count": len(exercises),
            "last_workout_date": _string(latest.get("workout_date")),
            "schema_version": FIRESTORE_SCHEMA_VERSION,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at_iso": now_iso,
        },
        merge=True,
    )


def _recompute_exercise_record(db, *, owner_uuid: str, name_key: str) -> None:
    normalized_key = _doc_key(name_key)
    record_ref = _exercise_records_collection(db, owner_uuid).document(normalized_key)
    exercises = _list_owner_exercises_for_name(db, owner_uuid=owner_uuid, name_key=normalized_key)
    records = _aggregate_records(exercises)
    if not records:
        record_ref.delete()
        return
    record = records[0]
    record_ref.set(
        {
            **record,
            "uid": owner_uuid,
            "exercise_name_key": normalized_key,
            "schema_version": FIRESTORE_SCHEMA_VERSION,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at_iso": _utc_now_iso(),
        },
        merge=True,
    )


def _sync_exercise_rollups(db, *, owner_uuid: str, name_keys: set[str]) -> None:
    for name_key in {key for key in name_keys if key}:
        _sync_user_exercise_definition(db, owner_uuid=owner_uuid, name_key=name_key)
        _recompute_exercise_record(db, owner_uuid=owner_uuid, name_key=name_key)


def create_exercise(db, *, owner_uuid: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = _normalize_text(payload.get("name"), max_len=160)
    if not name:
        raise ValueError("Exercise name is required.")
    workout_date_iso = resolve_workout_date(payload.get("workout_date")).isoformat()
    now_iso = _utc_now_iso()
    exercise_ref = _exercise_entries_collection(db, owner_uuid, workout_date_iso).document()
    doc = _entry_storage_doc(
        owner_uuid=owner_uuid,
        exercise_id=exercise_ref.id,
        workout_date_iso=workout_date_iso,
        order_index=_next_order_index(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso),
        name=name,
        category=payload.get("category"),
        movement_type=payload.get("movement_type"),
        notes=payload.get("notes"),
        sets=payload.get("sets"),
        created_at_iso=now_iso,
        updated_at_iso=now_iso,
        timezone_name=payload.get("timezone"),
        validate_sets=True,
    )
    doc["created_at"] = firestore.SERVER_TIMESTAMP
    exercise_ref.set(doc, merge=True)
    _recompute_workout_day(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)
    _sync_exercise_rollups(db, owner_uuid=owner_uuid, name_keys={_string(doc.get("name_key"))})
    return _serialize_exercise(exercise_ref.id, doc)


def update_exercise(db, *, owner_uuid: str, exercise_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
    existing = snap.to_dict() or {}
    old_workout_date = _string(existing.get("workout_date"))
    old_name_key = _doc_key(existing.get("name_key") or existing.get("name"))
    next_name = _normalize_text(payload.get("name"), max_len=160) if "name" in payload else _normalize_text(existing.get("name"), max_len=160)
    if not next_name:
        raise ValueError("Exercise name is required.")
    next_workout_date = resolve_workout_date(payload.get("workout_date")).isoformat() if "workout_date" in payload else old_workout_date
    next_order = (
        _next_order_index(db, owner_uuid=owner_uuid, workout_date_iso=next_workout_date)
        if next_workout_date != old_workout_date
        else _safe_order(existing.get("order_index"))
    )
    now_iso = _utc_now_iso()
    next_doc = _entry_storage_doc(
        owner_uuid=owner_uuid,
        exercise_id=_string(exercise_id),
        workout_date_iso=next_workout_date,
        order_index=next_order,
        name=next_name,
        category=payload.get("category") if "category" in payload else existing.get("category"),
        movement_type=payload.get("movement_type") if "movement_type" in payload else existing.get("movement_type"),
        notes=payload.get("notes") if "notes" in payload else existing.get("notes"),
        sets=payload.get("sets") if "sets" in payload else existing.get("sets"),
        created_at_iso=_string(existing.get("created_at_iso")) or now_iso,
        updated_at_iso=now_iso,
        timezone_name=payload.get("timezone") if "timezone" in payload else existing.get("timezone"),
        validate_sets="sets" in payload,
    )
    if existing.get("created_at") is not None:
        next_doc["created_at"] = existing.get("created_at")
    else:
        next_doc["created_at"] = firestore.SERVER_TIMESTAMP

    if next_workout_date == old_workout_date:
        snap.reference.set(next_doc, merge=True)
    else:
        new_ref = _exercise_entry_ref(db, owner_uuid, next_workout_date, _string(exercise_id))
        batch = db.batch()
        batch.set(new_ref, next_doc, merge=True)
        batch.delete(snap.reference)
        batch.commit()
    _recompute_workout_day(db, owner_uuid=owner_uuid, workout_date_iso=old_workout_date)
    if next_workout_date != old_workout_date:
        _recompute_workout_day(db, owner_uuid=owner_uuid, workout_date_iso=next_workout_date)
    _sync_exercise_rollups(db, owner_uuid=owner_uuid, name_keys={old_name_key, _string(next_doc.get("name_key"))})
    return _serialize_exercise(_string(exercise_id), next_doc)


def delete_exercise(db, *, owner_uuid: str, exercise_id: str) -> None:
    snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
    existing = snap.to_dict() or {}
    workout_date_iso = _string(existing.get("workout_date"))
    name_key = _doc_key(existing.get("name_key") or existing.get("name"))
    snap.reference.delete()
    _recompute_workout_day(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)
    _sync_exercise_rollups(db, owner_uuid=owner_uuid, name_keys={name_key})


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

    snapshots = []
    for exercise_id in normalized_ids:
        snap = _exercise_snapshot_for_owner(db, owner_uuid=owner_uuid, exercise_id=exercise_id)
        if _string((snap.to_dict() or {}).get("workout_date")) != workout_date_iso:
            raise ValueError("Reorder includes an exercise from a different day.")
        snapshots.append(snap)

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

    for index, snap in enumerate(snapshots):
        batch.set(
            snap.reference,
            {"order_index": index, "updated_at": firestore.SERVER_TIMESTAMP, "updated_at_iso": now_iso},
            merge=True,
        )
        pending += 1
        updates += 1
        commit_if_needed()
    commit_if_needed(force=True)
    _recompute_workout_day(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)
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


def _summary_from_day_doc(data: dict[str, Any] | None, fallback_exercises: list[dict[str, Any]]) -> dict[str, Any]:
    if not data:
        return _summary_from_exercises(fallback_exercises)
    return {
        "total_volume": round(float(data.get("total_volume") or 0), 2),
        "sets_completed": int(data.get("sets_completed") or 0),
        "exercise_count": int(data.get("exercise_count") or 0),
    }


def build_day_payload(db, *, auth_user: dict[str, Any], workout_date: Any = None) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    selected_date = resolve_workout_date(workout_date)
    workout_date_iso = selected_date.isoformat()
    exercises = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=workout_date_iso)
    day_snap = _workout_day_ref(db, owner_uuid, workout_date_iso).get()
    return {
        "user": profile,
        "day": _day_labels(selected_date),
        "summary": _summary_from_day_doc(day_snap.to_dict() if day_snap.exists else None, exercises),
        "exercises": exercises,
    }


def _default_catalog_docs() -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(DEFAULT_EXERCISE_LIBRARY):
        name = _normalize_text(item.get("name"), max_len=160)
        if not name:
            continue
        category, movement_type = _coalesce_exercise_metadata(
            name=name,
            category=item.get("category"),
            movement_type=item.get("movement_type"),
        )
        key = _doc_key(name)
        docs[key] = {
            "name": name,
            "name_key": key,
            "category": category,
            "category_key": _category_key(category),
            "movement_type": movement_type,
            "movement_type_key": _movement_type_key(movement_type),
            "type": movement_type,
            "source": "default",
            "active": True,
            "aliases": [],
            "sort_name": key,
            "sort_order": index,
            "schema_version": FIRESTORE_SCHEMA_VERSION,
        }
    return docs


def _ensure_exercise_catalog_seeded(db) -> None:
    catalog = db.collection(EXERCISE_CATALOG_COLLECTION)
    expected = _default_catalog_docs()
    existing = {snap.id: (snap.to_dict() or {}) for snap in catalog.stream()}
    batch = db.batch()
    pending = 0
    now_iso = _utc_now_iso()

    def commit_if_needed(force: bool = False):
        nonlocal batch, pending
        if pending == 0:
            return
        if force or pending >= _WRITE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            pending = 0

    for key, doc in expected.items():
        current = existing.get(key) or {}
        comparable = {field: current.get(field) for field in doc}
        if comparable == doc:
            continue
        payload = {
            **doc,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at_iso": now_iso,
        }
        if not current:
            payload["created_at"] = firestore.SERVER_TIMESTAMP
            payload["created_at_iso"] = now_iso
        batch.set(catalog.document(key), payload, merge=True)
        pending += 1
        commit_if_needed()
    commit_if_needed(force=True)


def _list_catalog_options(db) -> list[dict[str, Any]]:
    _ensure_exercise_catalog_seeded(db)
    rows = []
    for snap in db.collection(EXERCISE_CATALOG_COLLECTION).stream():
        data = snap.to_dict() or {}
        if data.get("active") is False:
            continue
        name = _normalize_text(data.get("name"), max_len=160)
        if not name:
            continue
        category, movement_type = _coalesce_exercise_metadata(
            name=name,
            category=data.get("category"),
            movement_type=data.get("movement_type"),
        )
        rows.append(
            {
                "name": name,
                "category": category,
                "movement_type": movement_type,
                "type": movement_type,
                "source": _string(data.get("source")) or "default",
                "_rank": "",
            }
        )
    if rows:
        return rows
    return [
        {
            "name": doc["name"],
            "category": doc["category"],
            "movement_type": doc["movement_type"],
            "type": doc["movement_type"],
            "source": "default",
            "_rank": "",
        }
        for doc in _default_catalog_docs().values()
    ]


def _list_user_exercise_definition_options(db, *, owner_uuid: str) -> list[dict[str, Any]]:
    rows = []
    for snap in _exercise_definitions_collection(db, owner_uuid).stream():
        data = snap.to_dict() or {}
        name = _normalize_text(data.get("name"), max_len=160)
        if not name:
            continue
        category, movement_type = _coalesce_exercise_metadata(
            name=name,
            category=data.get("category"),
            movement_type=data.get("movement_type"),
        )
        rows.append(
            {
                "name": name,
                "category": category,
                "movement_type": movement_type,
                "type": movement_type,
                "source": "custom",
                "_rank": _string(data.get("updated_at_iso")) or _string(data.get("last_workout_date")),
            }
        )
    return rows


def list_exercise_options(db, *, auth_user: dict[str, Any]) -> dict[str, Any]:
    profile, owner_uuid = _owner_uuid_from_user(db, auth_user)
    merged: dict[str, dict[str, Any]] = {}
    for item in [*_list_catalog_options(db), *_list_user_exercise_definition_options(db, owner_uuid=owner_uuid)]:
        key = _doc_key(item.get("name"))
        rank = _string(item.get("_rank"))
        existing = merged.get(key)
        if existing is None or rank >= _string(existing.get("_rank")):
            merged[key] = item

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
    total_duration_seconds = 0.0
    total_distance_miles = 0.0
    completed_sets = 0
    max_weight = 0.0
    max_one_rm = 0.0
    movement_type = exercise.get("movement_type") or exercise.get("type") or "Strength"
    best_set = {"weight": None, "reps": None, "rpe": None, "duration_seconds": None, "distance_miles": None, "side": "", "volume": 0.0, "one_rm": 0.0}
    for set_row in exercise.get("sets") or []:
        weight = _safe_float(set_row.get("weight"))
        reps = _safe_int(set_row.get("reps"))
        rpe = _safe_float(set_row.get("rpe"))
        duration_seconds = _set_duration_seconds(set_row)
        distance_miles = _set_distance_miles(set_row)
        volume = _set_volume(weight, reps) if _is_strength_movement(movement_type) else 0.0
        one_rm = _set_calculated_one_rm(weight, reps)
        if _set_is_complete(set_row, movement_type):
            completed_sets += 1
        total_volume += volume
        total_duration_seconds += duration_seconds
        total_distance_miles += distance_miles
        if _is_strength_movement(movement_type) and weight is not None:
            max_weight = max(max_weight, float(weight))
        if _is_strength_movement(movement_type) and one_rm > max_one_rm:
            max_one_rm = one_rm
            best_set = {
                "weight": weight,
                "reps": reps,
                "rpe": rpe,
                "duration_seconds": round(duration_seconds, 2) if duration_seconds > 0 else None,
                "distance_miles": round(distance_miles, 3) if distance_miles > 0 else None,
                "side": _normalize_text(set_row.get("side"), max_len=40),
                "volume": round(volume, 2),
                "one_rm": round(one_rm, 2),
            }
    return {
        "total_volume": round(total_volume, 2),
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_distance_miles": round(total_distance_miles, 3),
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


def _filter_workout_days_by_range(days: list[dict[str, Any]], *, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
    if start_date is None and end_date is None:
        return list(days)
    output = []
    for day_row in days:
        workout_date = _parse_iso_date(day_row.get("date"))
        if workout_date is None:
            continue
        if start_date and workout_date < start_date:
            continue
        if end_date and workout_date > end_date:
            continue
        output.append(day_row)
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
    duration_seconds = _set_duration_seconds(best_set)
    distance_miles = _set_distance_miles(best_set)
    parts = []
    if duration_seconds > 0:
        if duration_seconds < 60:
            parts.append(f"{duration_seconds:g} sec")
        else:
            parts.append(f"{duration_seconds / 60:g} min")
    if distance_miles > 0:
        parts.append(f"{distance_miles:g} mi")
    side = _normalize_text(best_set.get("side"), max_len=40)
    if side:
        parts.append(side)
    if parts:
        return " ".join(parts)
    return "-"


def _set_summary_label(set_row: dict[str, Any], movement_type: Any) -> str:
    if _is_cardio_movement(movement_type):
        parts = []
        duration_seconds = _set_duration_seconds(set_row)
        distance_miles = _set_distance_miles(set_row)
        if duration_seconds > 0:
            parts.append(f"{duration_seconds / 60:g} min" if duration_seconds >= 60 else f"{duration_seconds:g} sec")
        if distance_miles > 0:
            parts.append(f"{distance_miles:g} mi")
        rpe = _safe_float(set_row.get("rpe"))
        if rpe is not None:
            parts.append(f"RPE {rpe:g}")
        return " ".join(parts)
    if _is_stretching_movement(movement_type):
        parts = []
        duration_seconds = _set_duration_seconds(set_row)
        if duration_seconds > 0:
            parts.append(f"{duration_seconds / 60:g} min" if duration_seconds >= 60 else f"{duration_seconds:g} sec")
        side = _normalize_text(set_row.get("side"), max_len=40)
        if side:
            parts.append(side)
        rpe = _safe_float(set_row.get("rpe"))
        if rpe is not None:
            parts.append(f"RPE {rpe:g}")
        return " ".join(parts)
    weight = _safe_float(set_row.get("weight"))
    reps = _safe_int(set_row.get("reps"))
    if weight is not None and reps is not None and reps > 0:
        return f"{weight:g}x{reps}"
    if reps is not None and reps > 0:
        return f"{reps} reps"
    return ""


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


def _build_volume_progression_from_days(days: list[dict[str, Any]], *, category: Any = None) -> list[dict[str, Any]]:
    normalized_category = _normalize_volume_category(category)
    rows = []
    for day_row in sorted(days, key=lambda item: _string(item.get("date"))):
        date_iso = _string(day_row.get("date"))
        if not date_iso:
            continue
        if normalized_category == DEFAULT_VOLUME_CATEGORY:
            volume = float(day_row.get("total_volume") or 0)
        else:
            category_summary = (day_row.get("category_summaries") or {}).get(normalized_category) or {}
            volume = float(category_summary.get("total_volume") or 0)
        rows.append({"date": date_iso, "date_label": _format_date_short(date_iso), "volume": round(volume, 2)})
    return rows


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


def _build_volume_category_options_from_days(days: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels: set[str] = set()
    for day_row in days:
        labels.update((day_row.get("category_summaries") or {}).keys())
    return [{"key": DEFAULT_VOLUME_CATEGORY, "label": "All categories"}, *[{"key": label, "label": label} for label in sorted(labels)]]


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


def _build_muscle_split_from_days(days: list[dict[str, Any]], *, metric: Any = None) -> list[dict[str, Any]]:
    metric_key = _normalize_muscle_split_metric(metric)
    by_group: dict[str, float] = defaultdict(float)
    by_group_days: dict[str, set[str]] = defaultdict(set)
    for day_row in days:
        day_iso = _string(day_row.get("date"))
        for category, summary in (day_row.get("category_summaries") or {}).items():
            category_label = _normalize_category(category) or "Other"
            if metric_key == "volume":
                by_group[category_label] += float(summary.get("total_volume") or 0)
            elif metric_key == "total_sets":
                by_group[category_label] += float(summary.get("completed_sets") or 0)
            elif metric_key == "workout_days":
                if day_iso:
                    by_group_days[category_label].add(day_iso)
            else:
                by_group[category_label] += float(summary.get("exercise_count") or 0)
    if metric_key == "workout_days":
        by_group = defaultdict(float, {group: float(len(day_set)) for group, day_set in by_group_days.items()})
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
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    start = _parse_iso_date(range_payload.get("start_date"))
    end = _parse_iso_date(range_payload.get("end_date"))
    all_days = _list_owner_workout_days(db, owner_uuid=owner_uuid)
    filtered_days = _filter_workout_days_by_range(all_days, start_date=start, end_date=end)
    filtered = _list_owner_exercises_for_workout_days(db, owner_uuid=owner_uuid, workout_days=filtered_days)
    records = _aggregate_records(filtered)

    volume_category_options = _build_volume_category_options_from_days(all_days)
    normalized_volume_category = _normalize_volume_category(volume_category)
    allowed_categories = {row["key"] for row in volume_category_options}
    if normalized_volume_category not in allowed_categories:
        normalized_volume_category = DEFAULT_VOLUME_CATEGORY

    volume_progression_by_category: dict[str, list[dict[str, Any]]] = {}
    for option in volume_category_options:
        category_key = _string(option.get("key")) or DEFAULT_VOLUME_CATEGORY
        volume_progression_by_category[category_key] = _build_volume_progression_from_days(filtered_days, category=category_key)
    volume_progression = volume_progression_by_category.get(normalized_volume_category, [])
    total_volume = round(sum(float(item.get("volume") or 0) for item in volume_progression), 2)

    total_sets = sum(int(day_row.get("sets_completed") or 0) for day_row in filtered_days)
    exercise_names: set[str] = set()
    for exercise in filtered:
        exercise_names.add(_normalize_text(exercise.get("name"), max_len=160))

    muscle_split_by_metric = {
        _string(option["key"]): _build_muscle_split_from_days(filtered_days, metric=option["key"])
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
            "workout_days": len(filtered_days),
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
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    filtered_days = _filter_workout_days_by_range(
        _list_owner_workout_days(db, owner_uuid=owner_uuid),
        start_date=_parse_iso_date(range_payload.get("start_date")),
        end_date=_parse_iso_date(range_payload.get("end_date")),
    )
    filtered = _list_owner_exercises_for_workout_days(db, owner_uuid=owner_uuid, workout_days=filtered_days)
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
    result = {}
    for name in exercise_names:
        sessions = []
        for ex in _list_owner_exercises_for_name(db, owner_uuid=owner_uuid, name_key=_doc_key(name)):
            ex_date = _parse_iso_date(_string(ex.get("workout_date")))
            if ex_date is not None and ex_date < before_date:
                sessions.append(ex)
        if not sessions:
            continue
        latest = max(sessions, key=lambda item: _string(item.get("workout_date")))
        movement_type = latest.get("movement_type") or latest.get("type") or "Strength"
        parts = [_set_summary_label(set_row, movement_type) for set_row in latest.get("sets") or []]
        parts = [part for part in parts if part]
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
    previous_days = [
        day_row
        for day_row in _list_owner_workout_days(db, owner_uuid=owner_uuid)
        if (_parse_iso_date(day_row.get("date")) or date.max) < before
    ]
    if not previous_days:
        return {"user": profile, "previous_date": None, "previous_date_label": None, "exercises": []}
    previous_date = _string(previous_days[-1].get("date"))
    candidates = list_day_exercises(db, owner_uuid=owner_uuid, workout_date_iso=previous_date)
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
        raw_sets = [
            {
                "weight": _safe_float(s.get("weight")),
                "reps": _safe_int(s.get("reps")),
                "rpe": _safe_float(s.get("rpe")),
                "duration_seconds": _safe_float(s.get("duration_seconds")),
                "distance_miles": _safe_float(s.get("distance_miles")),
                "side": _normalize_text(s.get("side"), max_len=40),
            }
            for s in (ex.get("sets") or [])
        ]
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
    name_key = _doc_key(name)
    category = ""
    movement_type = ""
    sessions = []
    for ex in _list_owner_exercises_for_name(db, owner_uuid=owner_uuid, name_key=name_key):
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
    all_days = _list_owner_workout_days(db, owner_uuid=owner_uuid)
    range_payload = resolve_analytics_range(range_key=range_key, start_date=start_date, end_date=end_date)
    start = _parse_iso_date(range_payload.get("start_date"))
    end = _parse_iso_date(range_payload.get("end_date")) or _utc_now().date()
    filtered = _filter_workout_days_by_range(all_days, start_date=start, end_date=end)
    by_date: dict[str, float] = defaultdict(float)
    for day_row in filtered:
        date_iso = _string(day_row.get("date"))
        if date_iso:
            by_date[date_iso] += float(day_row.get("total_volume") or 0)
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
