import almanet

from . import _greeting


if __name__ == '__main__':
    almanet.serve_single(["localhost:4150"], _greeting.public.service)
