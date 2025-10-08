# Space Collision Prediction — Progress

## Space Collision Prediction — Progress

### 0) TL;DR
Backend is up with a SQLite DB, SQLAlchemy models, and a working `/satellites/` endpoint.  
Frontend scaffold exists (React + TS), but no 3D scene yet.

---

### 1) Project Overview
Web app to **predict** and **visualize** potential collisions between satellites, debris, and NEOs using:
- React + Three.js (3D globe + orbits + risk overlays)
- FastAPI (data/API)
- SQLite (dev) / PostgreSQL (prod)
- Future: SGP4 + ML (risk prediction), WebSockets, Celery/Redis

---

### 2) Tech Stack (planned)
**Frontend:** React + TypeScript, Three.js  
**Backend:** FastAPI, Python 3.8+, SQLAlchemy, Pydantic  
**Data:** SQLite (dev), Alembic (migrations later)  
**Future:** Celery + Redis (background jobs), WebSockets, scikit-learn

---

### 3) What’s Done (Phase 1)
- ✅ **DB setup** (`backend/database.py`)
  - SQLite engine + session factory
  - `Base.metadata.create_all(...)` creates tables
- ✅ **Models** (`backend/models.py`)
  - `Satellite` (id, catalog_number, name, TLE lines, last_updated)
  - `CollisionPrediction` (sat1_id, sat2_id, probability, predicted_time, distance_km)
- ✅ **API app + CORS** (`backend/main.py`)
  - FastAPI app with CORS for `http://localhost:5173`
  - Health/root check
  - `GET /satellites/` returns rows from DB
- ✅ **Response schema** (`backend/schemas.py`)
  - `SatelliteOut` (Pydantic) for clean JSON

### 4) In Progress / Not Started
- ⏳ **Frontend Three.js scene** — no Earth model or orbit rendering yet
- ⏳ **TLE ingestion & propagation (SGP4)**
- ⏳ **CRUD endpoints** for satellites & predictions
- ⏳ **Collision detection** (distance-based checks)
- ⏳ **ML models** (training/prediction endpoints)
- ⏳ **Background tasks + caching** (Celery/Redis)
- ⏳ **WebSockets** (real-time updates)
- ⏳ **Migrations** (Alembic)

---

### 5) How to Run (dev)
**Backend**
```bash
cd backend
uvicorn main:app --reload
# Docs: http://localhost:8000/docs
# Test: GET http://localhost:8000/satellites/