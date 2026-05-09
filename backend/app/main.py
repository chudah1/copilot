from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Copilot Investor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.auth import router as auth_router
app.include_router(auth_router)

from app.routes.portfolio import router as portfolio_router
app.include_router(portfolio_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
