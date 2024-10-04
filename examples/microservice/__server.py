import almanet

from . import _greeting


microservice = almanet.new_service_group("localhost:4150")
microservice.include(_greeting.public.example_service)
microservice.serve()
