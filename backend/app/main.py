from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.routes import (
    admin,
    auth,
    avito,
    bots,
    clients,
    dialogs,
    projects,
    telegram_sources,
    webhooks,
    personal_telegram_accounts,
)

app = FastAPI(title="Tuberry API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(bots.router, prefix="/api/bots", tags=["bots"])
app.include_router(dialogs.router, prefix="/api/dialogs", tags=["dialogs"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(avito.router, prefix="/api/avito", tags=["avito"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(telegram_sources.router, prefix="/api/telegram-sources", tags=["telegram-sources"])
app.include_router(
    personal_telegram_accounts.router,
    prefix="/api/personal-telegram-accounts",
    tags=["personal-telegram-accounts"],
)
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
