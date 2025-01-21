import almanet

from ._flow import *
from ._initial import *
from ._done import *


if __name__ == '__main__':
    almanet.serve(
        "localhost:4150",
        services=[
            public.service,
        ],
    )
