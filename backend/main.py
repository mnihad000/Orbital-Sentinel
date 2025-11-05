from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from database import get_db
from models import Satellite
from schemas import SatelliteOut, SatelliteCreate
from typing import List, Optional
import httpx, math
from datetime import datetime, timezone
from sgp4.api import Satrec, jday
from typing import List, Dict
from pydantic import BaseModel, Field, field_validator


app = FastAPI(title="Orbital Sentinel API", version="1.0.0")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"

def parse_tle(text):
    lines = []
    for l in text.splitlines():
        if l.strip():
            lines.append(l.strip())
    
    out = []
    i = 0
    while i+2<len(lines):
        name = lines[i]
        l1 = lines[i+1]
        l2 = lines[i+2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1
            continue

        norad = l1.split()[1]

        out.append({
            "norad_id": norad,
            "name": name,
            "l1": l1,
            "l2": l2
        })

        i += 3

    return out

def upsert_satellite_from_tle(db: Session, *, catalog_number: str, name: Optional[str], l1: str, l2: str) -> str:
    """
    Insert or update a satellite by NORAD catalog number.
    Returns 'created' or 'updated' or 'skipped' (if nothing changed).
    """
    # NOTE: if your model uses 'norad_id' instead of 'catalog_number', change the attribute below.
    existing = db.execute(
        select(Satellite).where(Satellite.catalog_number == catalog_number)
    ).scalar_one_or_none()

    if existing:
        changed = False
        if name and existing.name != name:
            existing.name = name; changed = True
        if existing.tle_line1 != l1:
            existing.tle_line1 = l1; changed = True
        if existing.tle_line2 != l2:
            existing.tle_line2 = l2; changed = True
        if changed:
            db.add(existing)
            return "updated"
        return "skipped"

    sat = Satellite(
        catalog_number=catalog_number,
        name=name,
        tle_line1=l1,
        tle_line2=l2,
    )
    db.add(sat)
    return "created"



# Calculates the Earth's rotation angle (Greenwich Mean Sidereal Time) in radians for a given UTC datetime
def gmst(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y,m,d = dt.year, dt.month, dt.day
    h = dt.hour + dt.minute/60 + dt.second/3600 + dt.microsecond/3.6e9
    if m <= 2: y -= 1; m += 12
    A = math.floor(y/100); B = 2 - A + math.floor(A/4)
    jd = math.floor(365.25*(y+4716)) + math.floor(30.6001*(m+1)) + d + B - 1524.5 + h/24.0
    T = (jd - 2451545.0)/36525.0
    gmst_deg = 280.46061837 + 360.98564736629*(jd-2451545) + 0.000387933*T*T - (T*T*T)/38710000.0
    return math.radians(gmst_deg % 360.0)

# ---- Schemas ----
class SatelliteBase(BaseModel):
    # accept either 'catalog_number' or 'norad_id' from clients
    catalog_number: Optional[str] = Field(None, examples=["12345"])
    norad_id: Optional[str] = Field(None, examples=["12345"])
    name: Optional[str] = Field(None, examples=["STARLINK-1234"])
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None

    @field_validator("catalog_number", mode="before")
    @classmethod
    def normalize_catalog(cls, v):
        # if client sends catalog_number explicitly, keep it; otherwise None here (we’ll fill from norad_id below)
        return v

    @field_validator("norad_id", mode="before")
    @classmethod
    def normalize_norad(cls, v):
        return v

    def get_catalog_number(self) -> Optional[str]:
        # prefer catalog_number; otherwise use norad_id
        return self.catalog_number or self.norad_id

class SatelliteCreate(SatelliteBase):
    # require at least an id plus two TLE lines to be useful
    tle_line1: str
    tle_line2: str

class SatelliteUpdate(BaseModel):
    catalog_number: Optional[str] = None
    norad_id: Optional[str] = None
    name: Optional[str] = None
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None

    def get_catalog_number(self) -> Optional[str]:
        return self.catalog_number or self.norad_id

class SatelliteOut(BaseModel):
    id: int
    catalog_number: str
    name: Optional[str] = None
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None

    class Config:
        from_attributes = True  # allows returning SQLAlchemy objects

def clamp_page(p: int) -> int:
    return 1 if p < 1 else p

def clamp_page_size(ps: int) -> int:
    return 10 if ps < 1 else 100 if ps > 100 else ps


# Converts satellite coordinates from the ECI (space-fixed) frame to the ECEF (Earth-fixed) frame using Earth's rotation angle
def eci_to_ecef(x,y,z,theta):
    c,s = math.cos(theta), math.sin(theta)
    return c*x + s*y, -s*x + c*y, z  # km

@app.get("/api/satellites")
async def satellites():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(CELESTRAK_URL)
        r.raise_for_status()
    return parse_tle(r.text)

@app.get("/api/positions")
async def api_positions(limit: int = Query(1000, ge=1, le=20000)):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(CELESTRAK_URL)
        r.raise_for_status()
    tles = parse_tle(r.text)[:limit]

    now = datetime.now(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute,
                  now.second + now.microsecond/1e6)
    theta = gmst(now)

    out = []
    for row in tles:
        try:
            sat = Satrec.twoline2rv(row["l1"], row["l2"])
            e, rvec, _ = sat.sgp4(jd, fr)
            if e != 0:
                continue
            x, y, z = eci_to_ecef(rvec[0], rvec[1], rvec[2], theta)
            out.append({
                "norad_id": row["norad_id"],
                "name": row["name"],
                "x": x, "y": y, "z": z,
                "epoch_iso": now.isoformat()
            })
        except Exception:
            continue
    return out

@app.post("/ingest/celestrak")
async def ingest_celestrak(
    url: Optional[str] = Query(None, description="Optional override of the Celestrak TLE URL"),
    db: Session = Depends(get_db),
):
    # fetch raw TLE text
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url or CELESTRAK_URL)
        r.raise_for_status()
    text = r.text

    # parse with your existing helper
    records = parse_tle(text)

    created = 0
    updated = 0
    skipped = 0
    malformed = 0

    # upsert each entry
    for rec in records:
        try:
            catalog = rec.get("norad_id")
            name = rec.get("name")
            l1 = rec.get("l1")
            l2 = rec.get("l2")

            if not (catalog and l1 and l2):
                malformed += 1
                continue

            result = upsert_satellite_from_tle(
                db,
                catalog_number=catalog,  # rename to 'norad_id=' if your column is named that
                name=name,
                l1=l1,
                l2=l2,
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1
        except Exception:
            # keep the ingest resilient; count and move on
            malformed += 1
            continue

    # single commit at the end for speed
    db.commit()

    return {
        "ok": True,
        "source": url or CELESTRAK_URL,
        "total_seen": len(records),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "malformed": malformed,
    }

# ---------- CREATE ----------
@app.post("/satellites", response_model=SatelliteOut, status_code=status.HTTP_201_CREATED)
def create_satellite(payload: SatelliteCreate, db: Session = Depends(get_db)):
    catalog = payload.get_catalog_number()
    if not catalog:
        raise HTTPException(status_code=422, detail="catalog_number or norad_id is required")

    # uniqueness check on catalog_number
    exists = db.execute(select(Satellite).where(Satellite.catalog_number == catalog)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="catalog_number already exists")

    sat = Satellite(
        catalog_number=catalog,
        name=payload.name,
        tle_line1=payload.tle_line1,
        tle_line2=payload.tle_line2,
    )
    db.add(sat)
    db.commit()
    db.refresh(sat)
    return sat

# ---------- READ (ONE) ----------
@app.get("/satellites/{sat_id}", response_model=SatelliteOut)
def get_satellite(sat_id: int, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="satellite not found")
    return sat

# ---------- UPDATE ----------
@app.put("/satellites/{sat_id}", response_model=SatelliteOut)
def update_satellite(sat_id: int, payload: SatelliteUpdate, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="satellite not found")

    # handle catalog_number change (enforce uniqueness)
    new_catalog = payload.get_catalog_number()
    if new_catalog and new_catalog != sat.catalog_number:
        conflict = db.execute(select(Satellite).where(Satellite.catalog_number == new_catalog)).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=409, detail="catalog_number already exists")
        sat.catalog_number = new_catalog

    # patch the rest
    if payload.name is not None:
        sat.name = payload.name
    if payload.tle_line1 is not None:
        sat.tle_line1 = payload.tle_line1
    if payload.tle_line2 is not None:
        sat.tle_line2 = payload.tle_line2

    db.commit()
    db.refresh(sat)
    return sat

# ---------- DELETE ----------
@app.delete("/satellites/{sat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_satellite(sat_id: int, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="satellite not found")
    db.delete(sat)
    db.commit()
    return None

# ---------- LIST (search + pagination) ----------
@app.get("/satellites", response_model=List[SatelliteOut])
def list_satellites_simple(
    search: Optional[str] = Query(None, description="Search by name or catalog_number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    q = select(Satellite)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            (Satellite.name.ilike(pattern)) | (Satellite.catalog_number.ilike(pattern))
        )

    q = q.order_by(Satellite.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(q).scalars().all()
    return rows

def compute_collisions(sat_positions: List[Dict], threshold_km: float = 1.0) -> List[Dict]:
    """
    Given a list of satellites with (x, y, z) positions in km,
    compute all pairs that are closer than threshold_km.
    """
    collisions = []
    n = len(sat_positions)
    for i in range(n):
        sat1 = sat_positions[i]
        for j in range(i + 1, n):  # avoid double comparisons
            sat2 = sat_positions[j]

            dx = sat2["x"] - sat1["x"]
            dy = sat2["y"] - sat1["y"]
            dz = sat2["z"] - sat1["z"]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            if dist < threshold_km:
                collisions.append({
                    "sat1": sat1["name"] or sat1["norad_id"],
                    "sat2": sat2["name"] or sat2["norad_id"],
                    "distance_km": round(dist, 3)
                })
    return collisions

def load_user_tles(db: Session, limit: int):
    """
    Load user satellites from DB and shape like Celestrak rows.
    """
    rows = db.query(Satellite).limit(limit).all()
    tles = []
    for s in rows:
        if not (s.tle_line1 and s.tle_line2):
            continue
        tles.append({
            "norad_id": str(s.catalog_number) if s.catalog_number else None,
            "name": s.name or f"user_sat_{s.id}",
            "l1": s.tle_line1,
            "l2": s.tle_line2,
            "db_id": s.id,
            "source": "user"
        })
    return tles


def store_collisions(db: Session, timestamp, collisions):
    """
    Save collisions to DB without duplicates.
    Duplicate = same pair (label order sorted) + same timestamp.
    """
    saved = []
    for c in collisions:
        # sort the pair alphabetically for uniqueness
        pair = sorted([c["name1"], c["name2"]])
        name1, name2 = pair
        exists = db.execute(
            select(CollisionPrediction).where(
                CollisionPrediction.satellite1_label == name1,
                CollisionPrediction.satellite2_label == name2,
                CollisionPrediction.predicted_time == timestamp
            )
        ).scalar_one_or_none()
        if exists:
            continue

        row = CollisionPrediction(
            satellite1_label=name1,
            satellite2_label=name2,
            distance_km=c["distance_km"],
            predicted_time=timestamp
        )
        db.add(row)
        saved.append(row)

    db.commit()
    return saved


@app.get("/api/collisions")
async def api_collisions(
    limit: int = Query(300, ge=10, le=2000, description="How many satellites to check"),
    threshold_km: float = Query(1.0, ge=0.01, le=50.0, description="Collision distance threshold (km)"),
    db: Session = Depends(get_db)
):
    """
    Combine user and Celestrak satellites, compute collisions,
    save unique results, and return them cleanly.
    """
    # 1) user satellites
    user_tles = load_user_tles(db, limit)

    # 2) Celestrak satellites
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(CELESTRAK_URL)
        r.raise_for_status()
    celestrak_tles = parse_tle(r.text)[:limit]
    for s in celestrak_tles:
        s["source"] = "celestrak"

    # 3) merge
    all_tles = user_tles + celestrak_tles

    # 4) get time + positions
    now = datetime.now(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour,
                  now.minute, now.second + now.microsecond / 1e6)
    theta = gmst(now)

    positions = []
    for row in all_tles:
        try:
            sat = Satrec.twoline2rv(row["l1"], row["l2"])
            e, rvec, _ = sat.sgp4(jd, fr)
            if e != 0:
                continue
            x, y, z = eci_to_ecef(rvec[0], rvec[1], rvec[2], theta)
            positions.append({
                "name": row["name"],
                "x": x, "y": y, "z": z,
                "source": row["source"]
            })
        except Exception:
            continue

    # 5) reuse existing compute_collisions
    collisions = compute_collisions(positions, threshold_km)

    # 6) save to DB
    saved = store_collisions(db, now, collisions)

    # 7) clean, readable return
    result = {
        "timestamp": now.isoformat(),
        "threshold_km": threshold_km,
        "total_checked": len(positions),
        "collision_count": len(saved),
        "collisions": []
    }

    for c in saved:
        result["collisions"].append({
            "satellite1_label": c.satellite1_label,
            "satellite2_label": c.satellite2_label,
            "distance_km": c.distance_km,
            "predicted_time": c.predicted_time.isoformat()
        })

    return result




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)