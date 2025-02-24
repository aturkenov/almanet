# almanet

Web Messaging Protocol is an open application level protocol that provides two messaging patterns:
- Routed Remote Procedure Calls (RPC)
- Produce & Consume

Almanet uses NSQ to exchange messages between different sessions. [NSQ](https://nsq.io/) is a realtime distributed queue like message broker.

## Installation

Before install and run NSQD instance [using this instruction](https://nsq.io/overview/quick_start.html).

Then install [`almanet` PyPI package](https://pypi.org/project/almanet/)

```sh
pip install almanet
```

## Usage

- [How to build microservices?](guide/microservice/README.md)
- [How to call remote procedure?](guide/calling/README.md)
