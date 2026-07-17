from fastapi import APIRouter

from ..content.learn_content import LEARN_CONTENT
from ..schemas import LearnContent

router = APIRouter(prefix="/api/learn", tags=["learn"])


@router.get("/content", response_model=LearnContent)
async def get_learn_content():
    return LEARN_CONTENT
