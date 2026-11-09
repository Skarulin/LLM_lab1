import sqlite3

from db import DB_PATH
from schemas import ProductQuery


def search_products(query: ProductQuery):
    if query.category == "other":
        return {
            "status": "unsupported_category",
            "items": [],
            "message": "Категория не поддерживается. Доступны: ноутбуки, смартфоны, планшеты.",
        }

    sql = "SELECT id, name, category, price FROM products WHERE category = ?"
    params = [query.category]
    if query.max_price is not None:
        sql += " AND price <= ?"
        params.append(query.max_price)

    order = "DESC" if query.sort_by == "price_desc" else "ASC"
    sql += f" ORDER BY price {order}"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        items = [dict(row) for row in conn.execute(sql, params)]

    if not items:
        return {"status": "empty", "items": [], "message": "Ничего не найдено."}
    return {"status": "ok", "items": items}