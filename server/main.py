import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect().close()  # ensure schema exists at startup
    yield


app = FastAPI(title="watch-app", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "db": db.db_path()}
