# almanet

Web Messaging Protocol is an open application level protocol that provides two messaging patterns:
- Routed Remote Procedure Calls (RPC)
- Produce & Consume

[NSQ](https://nsq.io/) is a realtime distributed queue like message broker.

Almanet uses NSQ to exchange messages between different sessions.

## Quick Start

Before install and run NSQD instance [using this instruction](https://nsq.io/overview/quick_start.html).

Then install [`almanet` PyPI package](https://pypi.org/project/almanet/)

```sh
pip install almanet
```

or

```sh
poetry add almanet
```

Create a new file and

```python
import almanet
```

### Create your own Microservice

<details>
<summary>Explanation of the code that defines and runs a simple microservice</summary>

#### Define your instance of microservice
```python
example_service = almanet.new_service(
    "localhost:4150",
    prepath="net.example"
)
```

_Arguments_:
- the TCP addresses of the NSQ instances
- prepath for the service's procedures, helping in identifying and organizing them

#### Define your custom exception
```python
class denied(almanet.rpc_error):
    """Custom RPC exception"""
```

This custom exception can be raised within procedures to signal specific error conditions to the caller.

#### Define your remote procedure to call
```python
@example_service.procedure
async def greeting(
    session: almanet.Almanet,
    payload: str,
) -> str:
    """Procedure that returns greeting message"""
    if payload == "guest":
        raise denied()
    return f"Hello, {payload}!"
```

Decorator `@example_service.procedure` registers the `greeting` function as a remote procedure for the `example_service`.

Arguments:
- payload is a data that was passed during invocation.
- session is a joined service, instance of `almanet.Almanet`

It raises the custom denied exception, indicating that this payload is not allowed if `payload` is `"guest"`.
Otherwise, it returns a greeting message.

#### At the end of the file
```python
if __name__ == "__main__":
    example_service.serve()
```

Starts the service, making it ready to handle incoming RPC requests.

#### Finally

Run your module using the python command
</details>

### Call your Microservice

<details>
<summary>Explanation of the code for creating a new session, calling a remote procedure, and handling potential exceptions during the invocation.</summary>

#### Create a new session
```python
session = almanet.new_session("localhost:4150")
```

_Arguments_:
- the TCP addresses of the NSQ instances

#### Calling the Remote Procedure
```python
async with session:
    result = await session.call("net.example.greeting", "Aidar")
    print(result.payload)
```

`async with session` ensures that the session is properly managed and closed after use.
Calls the remote procedure `net.example.greeting` with the payload `"Aidar"`.
Raises `TimeoutError` if procedure not found or request timed out.
`result.payload` contains the result of the procedure execution.

#### Catching remote procedure exceptions
```python
async with session:
    try:
        await session.call("net.example.greeting", "guest")
    except almanet.rpc_error as e:
        print("during call net.example.greeting('guest'):", e)
```

The `try` block attempts to call the `net.example.greeting` procedure with the payload `"guest"`.
If an exception occurs during the call, specifically an `almanet.rpc_error`,
it is caught by the `except` block.

#### Finally

Run your module using the python command
</details>

<br />

See the full examples in [`./examples`](/examples) directory.
