import typing

import pydantic


__all__ = [
    "extract_annotations",
    "generate_json_schema",
    "describe_function",
]


def extract_annotations(
    function: typing.Callable,
):
    payload_annotation = function.__annotations__.get('payload', ...)
    return_annotation = function.__annotations__.get('return', ...)
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
    f: typing.Callable,
    description: str | None = None,
    payload_model: typing.Any = ...,
    return_model: typing.Any = ...,
):
    """
    Returns a dictionary containing the description, payload model, and return model of the function.
    """
    if description is None:
        description = f.__doc__

    if payload_model is ...:
        payload_annotation = f.__annotations__.get('payload', ...)
    else:
        payload_annotation = payload_model

    payload_json_schema = generate_json_schema(payload_annotation)

    if return_model is ...:
        return_annotation = f.__annotations__.get('return', ...)
    else:
        return_annotation = return_model

    return_json_schema = generate_json_schema(return_annotation)

    return {
        'description': description,
        'payload_json_schema': payload_json_schema,
        'return_json_schema': return_json_schema,
    }
