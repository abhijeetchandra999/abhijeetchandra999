import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from crawler import audit_url

app = FastAPI(
    title="SEO & Link Verification Agent",
    description="Python API for auditing bad links, 4XX status codes, duplicate tags, missing image alt attributes, crawl blocks, and broken canonical links.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuditRequest(BaseModel):
    url: str
    max_pages: int = 25

@app.post("/api/audit")
async def perform_audit(request: AuditRequest):
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")
    
    url = request.url.strip()
    max_pages = min(max(1, request.max_pages), 100)
    try:
        results = await audit_url(url, max_pages=max_pages)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "SEO Link Audit Agent"}

# Serve static UI files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
