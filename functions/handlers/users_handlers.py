from firebase_functions import https_fn
from routes.users import create_users_app

usersApp = create_users_app()

@https_fn.on_request()
def users(req: https_fn.Request) -> https_fn.Response:
    with usersApp.request_context(req.environ):
        return usersApp.full_dispatch_request()
