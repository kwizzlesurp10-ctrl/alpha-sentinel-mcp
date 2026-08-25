from fastapi import FastAPI, Request

app = FastAPI(title="alpha-sentinel-min")


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def catch_all(request: Request, full_path: str = ""):
    return {
        "status": "healthy",
        "service": "alpha-sentinel",
        "build": "min-3-catchall",
        "path": request.url.path,
        "full_path": full_path,
        "method": request.method,
        "query": str(request.url.query),
    }


@app.get("/")
async def root():
    return {"status": "healthy", "at": "root"}
