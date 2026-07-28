from fastapi import FastAPI

from routers import discover, pipeline, stats

app = FastAPI(title="News Intelligence Platform API")
app.include_router(discover.router)
app.include_router(stats.router)
app.include_router(pipeline.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
