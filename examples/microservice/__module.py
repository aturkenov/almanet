import almanet

from . import _greeting

almanet.serve(
    "localhost:4150",
    services=[
        _greeting.public.service,
    ],
)
