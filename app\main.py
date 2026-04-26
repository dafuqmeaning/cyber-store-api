from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import create_session, get_session_user, verify_telegram_init_data
from .config import settings
from .db import db, init_db


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TelegramLoginRequest(BaseModel):
    init_data: str | None = None


class DemoLoginRequest(BaseModel):
    telegram_id: int = 10001
    username: str = "demo_buyer"
    first_name: str = "Demo"


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return get_session_user(authorization.removeprefix("Bearer ").strip())


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.post("/api/auth/telegram")
def telegram_login(payload: TelegramLoginRequest) -> dict:
    if not payload.init_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="init_data is required")
    return create_session(verify_telegram_init_data(payload.init_data))


@app.post("/api/auth/demo")
def demo_login(payload: DemoLoginRequest) -> dict:
    if not settings.allow_demo_auth:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo auth disabled")
    return create_session(payload.model_dump())


@app.get("/api/me")
def me(user: Annotated[dict, Depends(current_user)]) -> dict:
    return {"user": user}


@app.get("/api/categories")
def categories() -> dict:
    with db() as connection:
        rows = connection.execute("SELECT id, slug, name, accent FROM categories ORDER BY name").fetchall()
    return {"items": rows}


@app.get("/api/products")
def products(
    category: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=2)] = None,
) -> dict:
    where = []
    params: list[object] = []
    if category:
        where.append("categories.slug = ?")
        params.append(category)
    if q:
        where.append("(products.title LIKE ? OR products.description LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    sql = """
        SELECT
            products.id,
            products.title,
            products.description,
            products.price_cents,
            products.stock,
            products.image_url,
            products.is_adult,
            categories.slug AS category_slug,
            categories.name AS category_name,
            categories.accent AS category_accent
        FROM products
        JOIN categories ON categories.id = products.category_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY products.created_at DESC, products.id DESC"

    with db() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {"items": rows}


@app.get("/api/products/{product_id}")
def product(product_id: int) -> dict:
    with db() as connection:
        row = connection.execute(
            """
            SELECT
                products.id,
                products.title,
                products.description,
                products.price_cents,
                products.stock,
                products.image_url,
                products.is_adult,
                categories.slug AS category_slug,
                categories.name AS category_name,
                categories.accent AS category_accent
            FROM products
            JOIN categories ON categories.id = products.category_id
            WHERE products.id = ?
            """,
            (product_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"item": row}


@app.post("/api/orders/quote")
def quote_order(product_ids: list[int], user: Annotated[dict, Depends(current_user)]) -> dict:
    if not product_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty order")

    placeholders = ",".join("?" for _ in product_ids)
    with db() as connection:
        rows = connection.execute(
            f"SELECT id, title, price_cents, stock FROM products WHERE id IN ({placeholders})",
            product_ids,
        ).fetchall()

    total = sum(row["price_cents"] for row in rows)
    return {
        "buyer": user,
        "items": rows,
        "total_cents": total,
        "currency": "RUB",
        "status": "quote_only",
    }
