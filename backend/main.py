from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db
from models import Satellite
from schemas import SatelliteOut
from typing import List


app = FastAPI(title="Orbital Sentinel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Orbital Sentinel API is running!"}

@app.get("/satellites/")
def get_satellites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    satellites = db.query(Satellite).offset(skip).limit(limit).all()
    return satellites

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)