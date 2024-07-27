import typing

import pydantic


__all__ = [
    "extract_annotations",
    "generate_json_schema",
    "describe_function",
]


def extract_annotations(
    function: typing.Callable,
    payload_annotation=...,
    return_annotation=...,
):
    if payload_annotation is ...:
        payload_annotation = function.__annotations__.get("payload", ...)
    if return_annotation is ...:
        return_annotation = function.__annotations__.get("return", ...)
    return payload_annotation, return_annotation


def generate_json_schema(annotation):
    """
    Generates a JSON schema from an annotation.
    """
    if annotation is ...:
        return None

    model = pydantic.TypeAdapter(annotation)
    return model.json_schema()


def describe_function(
    target: typing.Callable,
    description: str | None = None,
    payload_annotation=...,
    return_annotation=...,
):
    """
    Generates a JSON schema from a function.
    """
    if description is None:
        description = target.__doc__
    payload_annotation, return_annotation = extract_annotations(target, payload_annotation, return_annotation)
    payload_json_schema = generate_json_schema(payload_annotation)
    return_json_schema = generate_json_schema(return_annotation)
    return {
        "description": description,
        "payload_json_schema": payload_json_schema,
        "return_json_schema": return_json_schema,
    }
