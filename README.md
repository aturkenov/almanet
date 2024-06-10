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

<details>
<summary>
<h3 id="create-microservice">Create your own Microservice</h3>
</summary>

Define your custom microservice
```python
example_service = almanet.new_service(
    <your nsqd tcp addresses>,
    prefix='net.example'
)
```

Define your custom exception
```python
class denied(almanet.rpc_error):
    """Custom RPC exception"""
```

Define your remote procedure to call
```python
@example_service.procedure
async def greeting(
    payload: str,  # is a data that was passed during invocation
    **kwargs,
) -> str:
    """Procedure that returns greeting message"""
    if payload == 'guest':
        # you can raise custom exceptions and the caller will have an error
        raise denied()
    return f'Hello, {payload}!'
```

At the end of file
```python
if __name__ == '__main__':
    example_service.serve()
```

Finally run your module using the python command
</details>

<details>
<summary>
<h3 id="call-microservice">Call your Microservice</h3>
</summary>

Create a new session
```python
session = almanet.new_session(<your nsqd tcp addresses>)
```

Then call the required remote procedure
```python
async with session:
    # Calling the `net.examples.greeting` procedure with 'Aidar' payload.
    # Raises `TimeoutError` if procedure not found or request timed out.
    result = await session.call('net.example.greeting', 'Aidar')
    print(result.payload)  # contains the result of the procedure execution
```

Catching remote procedure exceptions
```python
async with session:
    try:
        await session.call('net.example.greeting', 'guest')
    except almanet.rpc_error as e:
        print('during call net.example.greeting("guest"):', e)
```

Finally run your module using the python command
</details>

See the full examples in [`./examples`](/examples) directory.

<style>
h3 {
    display: inline-block;
    margin: 0;
}
</style>
