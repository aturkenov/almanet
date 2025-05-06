import almanet

from .__flow import *
from ._cancelled import *
from ._success import *


if __name__ == '__main__':
    almanet.serve_single(["localhost:4150"], public.service)
