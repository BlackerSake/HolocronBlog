from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserOut
from app.schemas.common import Response

router = APIRouter()

@router.get("/me", response_model=Response[UserOut])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return Response(data=current_user)