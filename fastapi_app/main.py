from config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, discover, pipeline, stats

app = FastAPI(title="News Intelligence Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discover.router)
app.include_router(stats.router)
app.include_router(pipeline.router)
app.include_router(auth.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
