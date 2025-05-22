import almanet

from . import _greeting


if __name__ == '__main__':
    almanet.serve_single(
        _greeting.public.service,
        almanet.clients.ansqd_tcp_client("localhost:4150"),
    )
