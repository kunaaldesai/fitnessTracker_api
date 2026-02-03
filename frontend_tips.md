# Frontend Migration Guide: Single-Document Workout Flow

We have refactored the backend to support a **"Save-on-Complete"** workflow. This reduces database writes and eliminates "ghost" workouts.

## Key Changes

1.  **No more progressive saves**: You no longer need to save the workout immediately upon starting, nor save every set individually.
2.  **Local State Management**: The frontend is now responsible for maintaining the entire state of the "active workout" in memory (or local storage) until the user hits "Finish" or "Save".
3.  **Single Endpoint**: You will send the entire workout data (including all exercises and sets) in one request.

## Workflow

### 1. Starting a Workout (from Template)

**Old Flow:**
*   Call `POST /users/{uid}/workouts/start` with `workout_id`.
*   Backend creates workout and copies exercises to subcollections.
*   Frontend fetches the new workout ID and loads it.

**New Flow:**
1.  **Fetch the Template**: Use `GET /getWorkout/{templateId}` to get the template details.
2.  **Initialize Local State**:
    *   Create a local object representing the active workout.
    *   Copy the `exercises` array from the template into your local state.
    *   Initialize empty `sets` arrays for each exercise.
    *   *Do not* call any "start" endpoint on the backend.

### 2. Tracking the Workout

*   As the user adds sets, checks boxes, or adds notes, **update your local state object**.
*   **Offline Support**: Since this is local state, it works perfectly offline. You may want to persist this state to `AsyncStorage` / `localStorage` in case the app is closed.

### 3. Saving the Workout

When the user clicks "Finish":

**Endpoint:** `POST /users/{uid}/workouts`

**Payload:**

```json
{
  "date": "2024-01-25",
  "notes": "Great session!",
  "timezone": "America/New_York",
  "workout_id": "template_id_123", // Optional: Link back to the original template
  "exercises": [
    {
      "exerciseId": "exercise_id_abc", // ID from the exercises collection
      "name": "Bench Press",
      "notes": "Felt heavy",
      "sets": [
        {
          "reps": 10,
          "weight": 135,
          "rir": 2, // Optional: Reps In Reserve
          "isPR": false // Optional: User flag
        },
        {
          "reps": 8,
          "weight": 145
        }
      ]
    },
    {
      "name": "Custom Exercise", // For ad-hoc exercises without an ID
      "sets": [...]
    }
  ]
}
```

**Response:**
Returns `{ "message": "Workout saved", "id": "new_workout_doc_id" }`.

### 4. Updating a Past Workout

**Endpoint:** `PUT /users/{uid}/workouts/{workoutId}`

To edit a workout, send the **full** structure again (or just the fields you want to update, but typically you'll send the whole updated `exercises` array).

```json
{
  "notes": "Updated notes",
  "exercises": [
    // Send the COMPLETE list of exercises and sets.
    // The backend replaces the old list with this one.
    {
      "exerciseId": "...",
      "sets": [...]
    }
  ]
}
```

### 5. Viewing Workouts

**Endpoint:** `GET /users/{uid}/workouts/{workoutId}`

*   Returns the full document, including the `exercises` and `sets` arrays nested inside.
*   No need to fetch subcollections!

## Summary of Deprecated Endpoints

The following endpoints are **removed** or **no longer used** for the active flow:

*   `POST .../workouts/start` (Behavior changed, prefer local start)
*   `POST .../items`
*   `GET .../items`
*   `POST .../sets`
*   `PUT .../sets/{id}`
