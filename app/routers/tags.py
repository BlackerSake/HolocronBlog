from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagUpdate, TagOut
from app.routers.crud import create_crud_router

router = create_crud_router(
    model=Tag,
    create_schema=TagCreate,
    update_schema=TagUpdate,
    output_schema=TagOut,
    prefix="/tags",
    tags=["Tags"],
    resource_name="tags",
    permission="tag:manage",
)