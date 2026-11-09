from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).with_name("catalog.db")

PRODUCTS = [
    # ноутбуки
    ("Ноутбук Lenovo IdeaPad 3", "laptop", 54_990),
    ("Ноутбук HP 15s", "laptop", 62_990),
    ("Ноутбук ASUS VivoBook 15", "laptop", 69_990),
    ("Ноутбук Acer Aspire 5", "laptop", 74_990),
    ("Ноутбук Lenovo ThinkPad E14", "laptop", 89_990),
    ("Ноутбук Apple MacBook Air M2", "laptop", 119_990),
    # смартфоны
    ("Смартфон Redmi Note 13", "smartphone", 19_990),
    ("Смартфон Samsung Galaxy A25", "smartphone", 24_990),
    ("Смартфон Realme 11 Pro", "smartphone", 27_990),
    ("Смартфон Google Pixel 7a", "smartphone", 49_990),
    ("Смартфон Samsung Galaxy S23", "smartphone", 69_990),
    ("Смартфон Apple iPhone 15", "smartphone", 89_990),
    # планшеты
    ("Планшет Digma Optima", "tablet", 10_990),
    ("Планшет Samsung Galaxy Tab A9", "tablet", 16_990),
    ("Планшет Xiaomi Redmi Pad SE", "tablet", 19_990),
    ("Планшет Lenovo Tab M10", "tablet", 22_990),
    ("Планшет Huawei MatePad 11", "tablet", 34_990),
    ("Планшет Apple iPad 10", "tablet", 44_990),
]


def init_db(path: Path = DB_PATH):
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name NVARCHAR(200) NOT NULL UNIQUE,
                category NVARCHAR(20) NOT NULL
                    CHECK (category IN ('laptop', 'smartphone', 'tablet')),
                price INTEGER NOT NULL CHECK (price >= 0)
            )
        """)
        conn.executemany(
            "INSERT OR IGNORE INTO products (name, category, price) VALUES (?, ?, ?)",
            PRODUCTS,
        )
        conn.commit()

if __name__ == "__main__":
    init_db()
    print(f"База создана: {DB_PATH}")