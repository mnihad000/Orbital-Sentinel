# Space Collision Prediction — Progress

## Space Collision Prediction — Progress

### 0) TL;DR

Backend is up with SQLite DB, SQLAlchemy models, working `/satellites/`, `/api/positions`, and `/api/collisions` endpoints.  
Frontend has a React + Three.js scene showing Earth, live satellite positions, and a “Deploy Satellite” UI box.

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
- ✅ **SGP4 + position computation**
  - `/api/positions` endpoint computes real-time (x, y, z)
- ✅ **Collision detection**
  - `/api/collisions` endpoint finds close satellite pairs
- ✅ **Frontend Earth + satellites**
  - React Three Fiber Earth + live satellite dots
- ✅ **Deploy Satellite UI**
  - “Deploy Satellite” box at top-left for creating custom satellites (frontend-only for now)

---

### 4) In Progress / Not Started

- ⏳ **TLE ingestion & propagation (SGP4)** — (live positions done; caching/DB ingest later)
- ⏳ **CRUD endpoints** for predictions
- ⏳ **ML models** (training/prediction endpoints)
- ⏳ **Background tasks + caching** (Celery/Redis)
- ⏳ **WebSockets** (real-time updates)
- ⏳ **Migrations** (Alembic)
- ⏳ **Frontend backend wiring for Deploy box**

---

### 🆕 5) Today’s Updates (Phase 2 Start)

**Goal:** connect FastAPI backend → React + Three.js frontend and render live satellite positions.

#### ✅ Backend Updates

- Added **Celestrak live TLE ingestion** (no API key required)
- Implemented **SGP4 orbit propagation** to compute real-time positions
- Added new endpoints:
  - `GET /api/positions?limit={n}` → returns `{x, y, z}` for each satellite
  - `GET /api/collisions` → computes close-approach pairs based on distance threshold
- Enabled **CORS** for both `localhost` and `127.0.0.1` (ports 3000, 5173)
- Verified backend via Swagger (`http://127.0.0.1:8000/docs`)

#### ✅ Frontend Updates

- Integrated **React Three Fiber (R3F)** rendering
- Added **Earth model (GLB)** + lights + environment
- Created **SatellitesCloud** component:
  - Fetches `/api/positions` every few seconds
  - Renders satellites as instanced white spheres in orbit
- Added **DeploySatelliteBox** (top-left UI)
  - Allows user input for custom satellite creation (frontend-only for now)
- Verified live data flow using browser DevTools and network logs

---

### 🔗 Current API Endpoints

| Endpoint                   | Method | Description                                             |
| -------------------------- | ------ | ------------------------------------------------------- |
| `/`                        | GET    | Root/health check                                       |
| `/satellites/`             | GET    | List satellites from database                           |
| `/api/satellites`          | GET    | Fetch parsed TLE data (from Celestrak)                  |
| `/api/positions?limit={n}` | GET    | Compute & return live satellite coordinates (`x, y, z`) |
| `/api/collisions`          | GET    | Detect potential close-approach pairs                   |
| `/docs`                    | GET    | Auto-generated Swagger UI                               |

---

### 6) How to Run (dev)

**Backend**

```bash
cd backend
uvicorn main:app --reload --port 8000
# Docs: http://127.0.0.1:8000/docs
```
4️⃣ Optional frontend Enhancements

If you want to push it further (and it’ll look impressive on your GitHub/portfolio):

🛰 Orbit Trails: draw curved lines to show recent motion.

🌎 Interactive Click: click a satellite to open a small info card (shows name, ID, altitude).

🔁 WebSocket integration: show real-time orbit updates.

🧠 ML Prediction Panel: small right-side panel that lists top “high-risk” objects, with a refresh button.