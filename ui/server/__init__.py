import fastapi
import fastapi.staticfiles
import fastapi.middleware.cors

from . import api_schema


server = fastapi.FastAPI()

server.add_middleware(
    fastapi.middleware.cors.CORSMiddleware,
    allow_credentials=True,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# server.mount(
#     '/static',
#     fastapi.staticfiles.StaticFiles(directory='./static', html=True),
#     name='static'
# )
server.include_router(api_schema.api_v1, prefix='/api')
