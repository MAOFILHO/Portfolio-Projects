"""Pydantic request schemas for the monolith. Flask doesn't validate request
bodies for free the way FastAPI does, so routes call `Model.model_validate()`
explicitly and turn a ValidationError into a 400 — the same validation
contract used by the BFF and by every microservice, for consistency."""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: str | None = None
    last_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    price: int = Field(gt=0)
    image: str | None = None


class OrderAddItemRequest(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
