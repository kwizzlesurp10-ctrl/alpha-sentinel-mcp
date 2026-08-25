from fastapi import FastAPI

app = FastAPI(title="alpha-sentinel-min")

@app.get("/")
@app.get("/api")
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "alpha-sentinel", "build": "min-2"}
