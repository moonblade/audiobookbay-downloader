from datetime import datetime

from auth import validate_user
from pydantic import BaseModel
from audiobookbay import get_torrents, search_audiobook, add_to_transmission
from fastapi import FastAPI, Query, HTTPException, Depends, status as httpstatus
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from utils import custom_logger
import uvicorn
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

logger = custom_logger(__name__)

security = HTTPBasic()
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    user = validate_user(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=httpstatus.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

@app.get("/")
def root(username: str = Depends(authenticate)):
    return FileResponse(os.path.join("static", "index.html"))

@app.get("/status")
def status():
    now = datetime.utcnow().isoformat() + "Z"
    return {"status": "ok", "timestamp": now}

@app.get("/search")
def search(
    query: str = Query(..., description="Search query"),
):
    """
    Searches a webpage based on the provided query and page number.
    """
    try:
        results = search_audiobook(query)
        return {"results": results}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

class TorrentRequest(BaseModel):
    url: str

@app.post("/add")
def add(
    torrent: TorrentRequest,
):
    """
    Adds a torrent to the download queue.
    """
    try:
        success = add_to_transmission(torrent.url)
        if success:
            return {"status": "ok", "message": "Torrent added successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add torrent")
    except Exception as e:
        logger.error(f"Add failed: {e}")
        raise HTTPException(status_code=500, detail="Add failed")

@app.get("/list")
def list():
    """
    Lists all torrents in the download queue.
    """
    return get_torrents()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True) 
