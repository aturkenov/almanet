# How to Build Microservices?

In this guide, we will show you how to build a simple greeting microservice using the Almanet library.

## Overview

In software engineering, a microservice architecture is an architectural pattern that organizes an application into a collection of loosely coupled, fine-grained services that communicate through lightweight protocols. This pattern is characterized by the ability to develop and deploy services independently, improving modularity, scalability, and adaptability.

The purpose of this microservice is to provide a simple greeting. It will expose an interface for other microservices to interact with and be run as a standalone service.

## Structure

The microservice will consist of three main components:

1. **Public Header File**: Contains public interfaces that define the functionality of the service.
2. **Implementation File**: Contains the actual logic behind the defined interfaces.
3. **Microservice File**: Contains the entry point to start the service.

### 1. Public Header File (`greeting.py`)

The public header ([the analogy with С++](https://learn.microsoft.com/en-us/cpp/cpp/header-files-cpp?view=msvc-170)) file is responsible for defining the interfaces that will be used by other modules to interact with the greeting microservice. Declare the available and not implemented functions, models, exceptions and other resources that your service will expose.

```python
# greeting.py
import almanet

__all__ = [
    "access_denied",
    "greet",
]

service = almanet.new_service(__name__)


class access_denied(almanet.rpc_error):
    """Custom RPC exception"""


@service.public_procedure
async def greet(payload: str) -> str:
    """
    Procedure that returns greeting message.

    Raises:
        - access_denied if `payload` is `"guest"`
    """
```

Use `almanet.new_service` function to create a new service.

Then declare the `greet` function that accepts and returns a string as payload,
then decorate it with the `@service.public_procedure` decorator.

Defined payload and return type annotations are used to validate the input and output of the `greet` function.

**Public Module**: Anyone can import and use this file, so it is important to keep the interface clean and straightforward.

### 2. Implementation File (`_greeting.py`)

The implementation file contains the logic that fulfills the interfaces defined in the public file. This is where the actual functionality resides.

```python
# _greeting.py
from . import greeting as public


@public.greet.implements
async def _greet(
    payload: str,  # is a data that was passed during invocation
    session,
) -> str:
    if payload == "guest":
        # you can raise custom exceptions
        # and the caller will have an error
        # see more about catching errors in `~/guide/calling/caller.py` file.
        raise public.access_denied()
    return f"Hello, {payload}!"

```

Import the related public header file as public.

Then implement the `greet` function and decorate with the `@public.greet.implements`,
where `public.greet` is a reference to the abstract `greet` procedure defined in the public header file above.

**Protected Module**: This file is meant for internal use only, so it should not be imported directly by external modules. Only protected or private modules can import this file.

### 3. Microservice File (`__microservice.py`)

The microservice file is the entry point to run the microservice. It contains the logic that starts the service and listens for incoming messages.

```python
# __microservice.py
import almanet

from . import _greeting

if __name__ == '__main__':
    almanet.serve(
        # message broker addresses
        "localhost:4150",  # nsqd tcp address
        services=[
            _greeting.public.service,
        ],
    )
```

Start the microservice using the `almanet.serve` function,
where the `services` parameter is a list of implemented (protected) services.

**Private Module**: This file is private and should not be imported by any other module. It serves solely as the entry point for running the microservice.

### 4. Running the Microservice

To run the greeting microservice, you can execute the following command:

```bash
python -m guide.microservice.__microservice
```

### Microservice Architecture Summary

- **`greeting.py`**: Public header file containing the interfaces to be used by other modules.
- **`_greeting.py`**: Implementation file containing the logic for the interfaces, for internal use only.
- **`__microservice.py`**: Private microservice file that starts the microservice, and is not intended to be imported by other modules.

By following this structure, we ensure that each component of the microservice is isolated based on its access level, maintaining a clean and modular design that is easy to scale and maintain.

### See Also:
- [Calling remote procedure](/guide/calling/README.md)
