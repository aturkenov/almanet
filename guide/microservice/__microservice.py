import almanet

from . import _greeting


if __name__ == '__main__':
    almanet.serve(
        "localhost:4150",
        services=[
            _greeting.public.service,
        ],
    )
