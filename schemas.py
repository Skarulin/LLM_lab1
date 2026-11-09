from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["laptop", "smartphone", "tablet", "other"]
SortBy = Literal["price_asc", "price_desc"]

class ProductQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    category: Category = Field(
        ...,
        description=(
            "Категория товара. Допустимые значения: laptop, smartphone, tablet, other. "
            "Если пользователь называет товар, не относящийся к ноутбукам, смартфонам "
            "или планшетам (например, холодильник), укажи other."
        ),
    )
    max_price: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Максимальная цена в рублях включительно. Целое неотрицательное число. "
            "Если пользователь не задал ограничение по цене, укажи null."
        ),
    )
    sort_by: SortBy = Field(
        default="price_asc",
        description=(
            "Направление сортировки по цене: price_asc — по возрастанию "
            "(сначала дешёвые), price_desc — по убыванию (сначала дорогие). "
            "Если направление не указано, используй price_asc."
        ),
    )