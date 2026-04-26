import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    accent TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    image_url TEXT NOT NULL,
    is_adult INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    expires_at INTEGER NOT NULL
);
"""


SEED_CATEGORIES = [
    ("home-tech", "Home Tech", "#42f5b0"),
    ("ritual", "Daily Ritual", "#ff3d81"),
    ("streetwear", "Streetwear", "#7c5cff"),
    ("desk", "Desk Setup", "#ffd166"),
]


SEED_PRODUCTS = [
    ("home-tech", "Neon Aroma Dock", "A compact diffuser dock with ambient light scenes.", 5490, 12, "https://images.unsplash.com/photo-1602928321679-560bb453f190?auto=format&fit=crop&w=900&q=80", 0),
    ("home-tech", "Pulse Smart Strip", "Modular power strip with app scenes and surge protection.", 7490, 8, "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=900&q=80", 0),
    ("ritual", "Cold Brew Lab Kit", "Glass brewer, filters, and a concentrated starter recipe card.", 4290, 20, "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=900&q=80", 0),
    ("ritual", "Midnight Tea Flight", "Four small-batch teas with tasting notes and storage tins.", 3190, 26, "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=900&q=80", 0),
    ("streetwear", "Signal Utility Cap", "Structured black cap with reflective thread and hidden pocket.", 2890, 15, "https://images.unsplash.com/photo-1521369909029-2afed882baee?auto=format&fit=crop&w=900&q=80", 0),
    ("streetwear", "Gridline Sling", "Water-resistant sling bag for phone, cards, and daily carry.", 6590, 9, "https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?auto=format&fit=crop&w=900&q=80", 0),
    ("desk", "Magnetic Cable Rail", "Desk-mounted rail that keeps charging cables exactly where needed.", 1990, 35, "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80", 0),
    ("desk", "Orbit Desk Light", "Slim LED task light with warm, neutral, and focus modes.", 8990, 6, "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=900&q=80", 0),
]


def _row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = _row_factory
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db() -> sqlite3.Connection:
    connection = connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript(SCHEMA)
        existing = connection.execute("SELECT COUNT(*) AS count FROM categories").fetchone()["count"]
        if existing:
            return

        connection.executemany(
            "INSERT INTO categories (slug, name, accent) VALUES (?, ?, ?)",
            SEED_CATEGORIES,
        )
        category_ids = {
            row["slug"]: row["id"]
            for row in connection.execute("SELECT id, slug FROM categories").fetchall()
        }
        connection.executemany(
            """
            INSERT INTO products (category_id, title, description, price_cents, stock, image_url, is_adult)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (category_ids[slug], title, description, price_cents, stock, image_url, is_adult)
                for slug, title, description, price_cents, stock, image_url, is_adult in SEED_PRODUCTS
            ],
        )
