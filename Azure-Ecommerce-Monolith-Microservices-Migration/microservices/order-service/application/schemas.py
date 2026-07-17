from pydantic import BaseModel, Field


class OrderAddItemRequest(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
