from fastapi import FastAPI

app = FastAPI(title="News Intelligence Platform API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
