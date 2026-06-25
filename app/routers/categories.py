from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut
from app.routers.crud import create_crud_router

router = create_crud_router(
    model=Category,
    create_schema=CategoryCreate,
    update_schema=CategoryUpdate,
    output_schema=CategoryOut,
    prefix="/categories",
    tags=["Categories"],
    resource_name="category",
)