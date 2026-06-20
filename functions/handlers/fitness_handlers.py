from firebase_functions import https_fn

from routes.fitness import create_fitness_app

fitness_app = create_fitness_app()


@https_fn.on_request()
def fitness(req: https_fn.Request) -> https_fn.Response:
    with fitness_app.request_context(req.environ):
        return fitness_app.full_dispatch_request()
