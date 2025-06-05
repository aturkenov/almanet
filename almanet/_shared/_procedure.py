from dataclasses import dataclass
import typing

import pydantic

from . import _decoding

__all__ = [
    "extract_annotations",
    "generate_json_schema",
    "generate_function_json_schema",
    "_function",
    "procedure_model",
]


def extract_annotations(
    function: typing.Callable,
    custom_payload_annotation=...,
    custom_return_annotation=...,
):
    if custom_payload_annotation is ...:
        custom_payload_annotation = function.__annotations__.get("payload", ...)
    if custom_return_annotation is ...:
        custom_return_annotation = function.__annotations__.get("return", ...)
    return custom_payload_annotation, custom_return_annotation


def generate_json_schema(annotation):
    """
    Generates a JSON schema from an annotation.
    """
    if annotation is ...:
        return None

    model = pydantic.TypeAdapter(annotation)
    return model.json_schema()


def generate_function_json_schema(
    target: typing.Callable,
    custom_name: str = ...,
    custom_description: str | None = None,
    custom_payload_annotation=...,
    custom_return_annotation=...,
):
    """
    Generates a JSON schema from a function.
    """
    if custom_name is ...:
        custom_name = target.__name__
    if custom_description is None:
        custom_description = target.__doc__
    custom_payload_annotation, custom_return_annotation = extract_annotations(
        target, custom_payload_annotation, custom_return_annotation
    )
    payload_json_schema = generate_json_schema(custom_payload_annotation)
    return_json_schema = generate_json_schema(custom_return_annotation)
    return {
        "name": custom_name,
        "description": custom_description,
        "payload": payload_json_schema,
        "return": return_json_schema,
    }


class _function[I, O](typing.Protocol):
    __name__: str

    async def __call__(
        self,
        payload: I,
        *args,
        **kwargs,
    ) -> O: ...


@dataclass(kw_only=True, slots=True)
class procedure_model[I, O]:
    function: _function[I, O]
    name: str = ...
    description: str | None = None
    tags: set[str] = ...
    validate: bool = True
    payload_model: typing.Any = ...
    return_model: typing.Any = ...
    exceptions: set[type[Exception]] = ...
    json_schema: typing.Mapping = ...
    serialize_payload: typing.Callable[[bytes | str], I] = _decoding.serialize_any_json
    serialize_return: typing.Callable[[bytes | str], O] = _decoding.serialize_any_json

    def __post_init__(self):
        if not callable(self.function):
            raise ValueError("decorated function must be callable")
        self.payload_model, self.return_model = extract_annotations(
            self.function, self.payload_model, self.return_model
        )
        self.json_schema = generate_function_json_schema(
            self.function,
            self.name,
            self.description,
            custom_payload_annotation=self.payload_model,
            custom_return_annotation=self.return_model,
        )
        self.name = self.json_schema["name"]
        self.description = self.json_schema["description"]
        if self.validate:
            self.serialize_payload = _decoding.serialize_json(self.payload_model)
            self.serialize_return = _decoding.serialize_json(self.return_model)
        if self.exceptions is ...:
            self.exceptions = set()
        if self.tags is ...:
            self.tags = set()
