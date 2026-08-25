from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"ok": True, "service": "alpha-sentinel"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "path": "/api/health"}
