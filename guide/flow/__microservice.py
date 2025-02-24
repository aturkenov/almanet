import almanet

from .__flow import *
from ._cancelled import *
from ._success import *


if __name__ == '__main__':
    almanet.serve(
        "localhost:4150",
        services=[
            public.service,
        ],
    )
