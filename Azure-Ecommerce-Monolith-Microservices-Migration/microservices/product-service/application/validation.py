"""Shared request-validation helper — same contract as monolith/app/validation.py
and every other service in this project, for consistency."""
from flask import jsonify
from pydantic import BaseModel, ValidationError


def validate_form(model_cls: type[BaseModel], form):
    try:
        return model_cls.model_validate(dict(form)), None
    except ValidationError as exc:
        return None, (jsonify({"message": "Validation error", "errors": exc.errors(include_url=False)}), 400)
