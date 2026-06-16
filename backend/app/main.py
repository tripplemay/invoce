"""FastAPI 应用入口。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.email_accounts import router as email_accounts_router
from app.api.health import router as health_router
from app.api.inbound import router as inbound_router
from app.api.invoices import router as invoices_router
from app.api.telegram import router as telegram_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(email_accounts_router)
app.include_router(invoices_router)
app.include_router(telegram_router)
app.include_router(inbound_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
