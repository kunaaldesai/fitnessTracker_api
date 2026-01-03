from firebase_functions import https_fn
from routes.workouts import create_workouts_app

workoutsApp = create_workouts_app()


@https_fn.on_request()
def workouts(req: https_fn.Request) -> https_fn.Response:
    with workoutsApp.request_context(req.environ):
        return workoutsApp.full_dispatch_request()
