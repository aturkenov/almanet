# Almanet

Web Messaging Protocol is an open application level protocol that provides two messaging patterns:
- Routed Remote Procedure Calls (RPC)
- Produce & Consume

NSQ is a realtime distributed message broker [(read more here)](https://nsq.io/).
And Almanet uses NSQ to exchange messages between different sessions.

[See more examples here.](/examples)

## Getting Started

Before install and run NSQD instance using this [instruction](https://nsq.io/overview/quick_start.html).

Create a new session
```python
session = almanet.new_session()
```

Join to your nsq network
```python
await session.join(<your nsqd tcp addresses>)
```

Define your custom exception
```python
class Denied(almanet.rpc_error):
    """Custom RPC exception"""
```

Define your remote procedure to call
```python
# First argument is a payload that was passed during invocation.
async def greeting(payload: str, **kwargs):
    """Procedure that returns greeting message"""
    if payload == 'guest':
        # you can raise custom exceptions and the caller will have an error
        raise Denied()
    return f'Hello, {payload}!'
```

Register your procedure in order to be called
```python
await session.register('net.example.greeting', greeting)
```

Call the procedure `net.examples.greeting` with 'Aidar' argument.
Raises `TimeoutError` if procedure not found or request timed out.
```python
result = await session.call('net.example.greeting', 'Aidar')
print(result.payload)
```

Or catch remote procedure exceptions
```python
try:
    await session.call('net.example.greeting', 'guest')
except almanet.rpc_error as e:
    print('during call net.example.greeting("guest"):', e)
```

Create `net.example.notification` consumer.
`almanet.consume` returns tuple[iterable messages, function that can stop consuming]
```python
messages_stream, stop_consumer = await session.consume(
    'net.example.notification', channel='test'
)
```

Start consuming messages and commit or rollback incoming message
```python
async for message in messages_stream:
    try:
        print('new event', message.body)
        # at the end of iteration commit message
        await message.commit()
    except:
        # if something went wrong
        await message.rollback()
```

Publish message to `net.example.notification` topic with 'hello, world' argument
```python
await session.produce('net.example.notification', 'hello, world')
```

Leave from network
```python
await session.leave()
```
