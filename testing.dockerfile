FROM python:3.12-bookworm

ENV TZ=UTC

RUN apt-get update
RUN apt-get install -y curl

WORKDIR /almanet

# installing nsq
RUN curl -o nsq-1.3.0.linux-amd64.go1.21.5.tar.gz https://s3.amazonaws.com/bitly-downloads/nsq/nsq-1.3.0.linux-amd64.go1.21.5.tar.gz
RUN tar -xzvf nsq-1.3.0.linux-amd64.go1.21.5.tar.gz
RUN mv nsq-1.3.0.linux-amd64.go1.21.5/bin/nsqd /bin/nsqd

# installing poetry
ENV POETRY_HOME=/opt/poetry
RUN pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock .
RUN poetry install --with testing --no-interaction

COPY . .

RUN ls -la

RUN nsqd &\
    python -m examples.microservice.__server &\
    pytest
