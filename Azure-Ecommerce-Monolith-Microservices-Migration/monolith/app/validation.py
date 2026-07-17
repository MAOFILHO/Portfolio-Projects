"""Shared request-validation helper: Flask routes call this instead of
reading request.form directly, so every write endpoint validates through the
same Pydantic contract used by the BFF."""
from flask import jsonify
from pydantic import BaseModel, ValidationError


def validate_form(model_cls: type[BaseModel], form):
    try:
        return model_cls.model_validate(dict(form)), None
    except ValidationError as exc:
        return None, (jsonify({"message": "Validation error", "errors": exc.errors(include_url=False)}), 400)
