# How to Call a Remote Procedure

In this guide, we will walk you through the process of calling a procedure from the [`guide.microservice.greeting`](../microservice/greeting.py).

### Step 1: Run the Microservice

Before calling the remote procedure, ensure that the `guide.microservice.greeting` microservice is up and running.
For detailed instructions on how to build and run your microservices, read the [How to Build Microservices?](../microservice/README.md) guide.

### Step 2: Import the Microservice Module

Next, import the [`guide.microservice`](../microservice/__init__.py) module. This module has already exposed the greeting procedure for public use.

```python
import guide.microservice
```

### Step 3: Write the Code to Call the Remote Procedure

In your Python script, create an asynchronous function to call the remote procedure. Here’s an example:

```python
import asyncio
import almanet

async def main():
    async with almanet.new_session("localhost:4150") as session:  # Connect to your network
        try:
            result = await session.call(guide.microservice.greet, "Aidar")  # Call the greeting procedure
            print(f"Result: {result}")  # Print the Result: 'Hello, Aidar'
        except almanet.rpc_error as e:
            print(f"Error calling procedure: {e}")

if __name__ == '__main__':
    asyncio.run(main())
```

In this code:

- The procedure `greet` is called on the `guide.microservice` module with the argument `"Aidar"`.
- The result, which should be `"Hello, Aidar"`, is printed.
- Any exceptions during the call are caught and printed.

### Step 4: Run the Caller Script

Once you've written the script, you can execute it to call the remote procedure. Use the following command:

```bash
python -m guide.calling.caller
```

With these steps, you should be able to successfully call the remote procedure from the `guide.microservice.greeting` microservice. Let me know if you run into any issues or have additional questions!
