from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from database import get_db
from models import Satellite, CollisionPrediction
from schemas import SatelliteOut, SatelliteCreate
from typing import List, Optional
import httpx, math, os
from datetime import datetime, timezone
from sgp4.api import Satrec, jday
from typing import List, Dict
from pydantic import BaseModel, Field, field_validator
import re


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
    satellites = (
        db.query(Satellite)
        .filter(Satellite.source == USER_SOURCE)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return satellites

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
SPACETRACK_BASE_URL = "https://www.space-track.org"
SPACETRACK_GP_TLE_PATH = (
    "/basicspacedata/query/class/gp/"
    "decay_date/null-val/"
    "epoch/%3Enow-10/"
    "orderby/norad_cat_id/"
    "format/tle"
)
PUBLIC_SOURCE = "spacetrack"
USER_SOURCE = "user"
PUBLIC_CACHE_SOURCES = (PUBLIC_SOURCE, "celestrak")


def load_local_env_file() -> None:
    """
    Lightweight support for the repo's api.env file without adding a dependency.
    Real deployments should set environment variables directly.
    """
    candidates = [
        os.path.join(os.getcwd(), "api.env"),
        os.path.join(os.getcwd(), "..", "api.env"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#") or "=" not in raw:
                        continue
                    key, value = raw.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            continue


load_local_env_file()


def get_spacetrack_credentials() -> tuple[Optional[str], Optional[str]]:
    username = os.getenv("SPACETRACK_USERNAME") or os.getenv("SPACETRACK_USER")
    password = os.getenv("SPACETRACK_PASSWORD") or os.getenv("SPACETRACK_PASS")
    if username and username.lower() in {"your_email", "your_username"}:
        username = None
    if password and password.lower() in {"your_password", "your_pass"}:
        password = None
    return username, password


async def fetch_tle_text(url: str, timeout: int = 30) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
        return r.text
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Celestrak. Check internet/DNS and try again.",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Celestrak request timed out.",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Celestrak returned HTTP {exc.response.status_code}.",
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch TLE data from Celestrak.",
        )


async def fetch_spacetrack_tle_text(timeout: int = 60) -> str:
    username, password = get_spacetrack_credentials()
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Space-Track credentials are not configured. Set "
                "SPACETRACK_USERNAME/SPACETRACK_PASSWORD or "
                "SPACETRACK_USER/SPACETRACK_PASS on the backend."
            ),
        )

    async with httpx.AsyncClient(base_url=SPACETRACK_BASE_URL, timeout=timeout) as client:
        try:
            login = await client.post(
                "/ajaxauth/login",
                data={"identity": username, "password": password},
            )
            login.raise_for_status()

            response = await client.get(SPACETRACK_GP_TLE_PATH)
            response.raise_for_status()
            if "<html" in response.text.lower():
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Space-Track returned an HTML response instead of TLE data.",
                )
            return response.text
        except HTTPException:
            raise
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Space-Track request timed out.",
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Space-Track returned HTTP {exc.response.status_code}.",
            )
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch TLE data from Space-Track.",
            )

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

        norad = l1[2:7].strip()

        out.append({
            "norad_id": norad,
            "name": name,
            "l1": l1,
            "l2": l2
        })

        i += 3

    return out

def upsert_satellite_from_tle(
    db: Session,
    *,
    catalog_number: str,
    name: Optional[str],
    l1: str,
    l2: str,
    source: str = USER_SOURCE,
) -> str:
    """
    Insert or update a satellite by NORAD catalog number.
    Returns 'created' or 'updated' or 'skipped' (if nothing changed).
    """
    # NOTE: if your model uses 'norad_id' instead of 'catalog_number', change the attribute below.
    existing = db.execute(
        select(Satellite).where(Satellite.catalog_number == catalog_number)
    ).scalar_one_or_none()

    if existing:
        if existing.source == USER_SOURCE and source != USER_SOURCE:
            return "skipped"
        changed = False
        if name and existing.name != name:
            existing.name = name; changed = True
        if existing.tle_line1 != l1:
            existing.tle_line1 = l1; changed = True
        if existing.tle_line2 != l2:
            existing.tle_line2 = l2; changed = True
        if existing.source != source:
            existing.source = source; changed = True
        if changed:
            existing.last_updated = datetime.utcnow()
            db.add(existing)
            return "updated"
        return "skipped"

    sat = Satellite(
        catalog_number=catalog_number,
        name=name,
        tle_line1=l1,
        tle_line2=l2,
        source=source,
        last_updated=datetime.utcnow(),
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
    source: Optional[str] = None

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
async def satellites(limit: int = Query(1000, ge=1, le=20000), db: Session = Depends(get_db)):
    records = load_cached_public_tles(db, limit)
    if not records:
        raise_empty_public_cache()
    return records


def raise_empty_public_cache():
    username, password = get_spacetrack_credentials()
    credential_detail = (
        "Space-Track credentials are not configured."
        if not username or not password
        else "Space-Track credentials are configured, but no cached public TLEs exist yet."
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"{credential_detail} Run POST /ingest/spacetrack to populate the local "
            "satellite cache before using live public positions."
        ),
    )


def shape_tle_from_satellite(row: Satellite, source: str) -> Optional[Dict]:
    if not (row.tle_line1 and row.tle_line2):
        return None
    l1, l2 = normalize_tle_pair(row.tle_line1, row.tle_line2)
    if not (l1 and l2):
        return None
    catalog = (
        _strip_wrapping_quotes(str(row.catalog_number))
        if row.catalog_number is not None
        else None
    )
    name = _strip_wrapping_quotes(row.name) if row.name else f"{source}_sat_{row.id}"
    return {
        "norad_id": catalog,
        "name": name,
        "l1": l1,
        "l2": l2,
        "db_id": row.id,
        "source": source,
    }


def load_cached_public_tles(db: Session, limit: int):
    rows = (
        db.query(Satellite)
        .filter(Satellite.source.in_(PUBLIC_CACHE_SOURCES))
        .order_by(Satellite.catalog_number.asc())
        .limit(limit)
        .all()
    )
    tles = []
    for row in rows:
        shaped = shape_tle_from_satellite(row, row.source or PUBLIC_SOURCE)
        if shaped:
            tles.append(shaped)
    return tles

@app.get("/api/positions")
async def api_positions(
    limit: int = Query(1000, ge=1, le=20000),
    db: Session = Depends(get_db),
):
    user_tles = load_user_tles(db, limit)
    public_tles = load_cached_public_tles(db, limit)
    if not user_tles and not public_tles:
        raise_empty_public_cache()
    all_tles = user_tles + public_tles

    now = datetime.now(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute,
                  now.second + now.microsecond/1e6)
    theta = gmst(now)

    out = []
    for row in all_tles:
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
                "source": row.get("source", PUBLIC_SOURCE),
                "epoch_iso": now.isoformat()
            })
        except Exception:
            continue
    return out


def _strip_wrapping_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        v = v[1:-1].strip()
    return v


def normalize_tle_pair(line1_raw: Optional[str], line2_raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Try to recover valid TLE line1/line2 from noisy input:
    - wraps in quotes
    - accidental multi-line paste into one field
    - duplicated line content
    """
    chunks = []
    for raw in (line1_raw, line2_raw):
        if raw is None:
            continue
        text = str(raw).replace("\\n", "\n")
        text = _strip_wrapping_quotes(text)
        chunks.extend(text.splitlines())

    line1 = None
    line2 = None
    for c in chunks:
        s = _strip_wrapping_quotes(c)
        if not s:
            continue
        if line1 is None and s.startswith("1 "):
            line1 = s
        if line2 is None and s.startswith("2 "):
            line2 = s

    if line1 is None and line1_raw is not None:
        s1 = _strip_wrapping_quotes(str(line1_raw)).strip()
        m1 = re.search(r"(1\s.+)", s1)
        if m1:
            line1 = _strip_wrapping_quotes(m1.group(1))
    if line2 is None and line2_raw is not None:
        s2 = _strip_wrapping_quotes(str(line2_raw)).strip()
        m2 = re.search(r"(2\s.+)", s2)
        if m2:
            line2 = _strip_wrapping_quotes(m2.group(1))

    return line1, line2


def tle_is_propagatable(line1: str, line2: str) -> bool:
    """
    Validate TLE by attempting SGP4 propagation at current UTC time.
    """
    try:
        sat = Satrec.twoline2rv(line1, line2)
        now = datetime.now(timezone.utc)
        jd, fr = jday(
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second + now.microsecond / 1e6,
        )
        e, rvec, _ = sat.sgp4(jd, fr)
        if e != 0:
            return False
        return all(math.isfinite(v) for v in rvec)
    except Exception:
        return False


def ingest_tle_records(db: Session, records: List[Dict], source: str) -> Dict:
    created = 0
    updated = 0
    skipped = 0
    malformed = 0

    for rec in records:
        try:
            catalog_raw = str(rec.get("norad_id") or "").strip()
            name = rec.get("name")
            l1 = rec.get("l1")
            l2 = rec.get("l2")

            if not (catalog_raw and catalog_raw.isdigit() and l1 and l2):
                malformed += 1
                continue

            result = upsert_satellite_from_tle(
                db,
                catalog_number=int(catalog_raw),
                name=name,
                l1=l1,
                l2=l2,
                source=source,
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1
        except Exception:
            malformed += 1
            continue

    db.commit()
    return {
        "total_seen": len(records),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "malformed": malformed,
    }

@app.post("/ingest/celestrak")
async def ingest_celestrak(
    url: Optional[str] = Query(None, description="Optional override of the Celestrak TLE URL"),
    enable_fallback: bool = Query(False, description="Explicitly enable disabled CelesTrak fallback ingest"),
    db: Session = Depends(get_db),
):
    if not enable_fallback:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="CelesTrak ingest is disabled by default. Use POST /ingest/spacetrack.",
        )

    # fetch raw TLE text
    text = await fetch_tle_text(url or CELESTRAK_URL, timeout=60)

    # parse with your existing helper
    records = parse_tle(text)
    counts = ingest_tle_records(db, records, source="celestrak")

    return {
        "ok": True,
        "source": url or CELESTRAK_URL,
        **counts,
    }


@app.post("/ingest/spacetrack")
async def ingest_spacetrack(db: Session = Depends(get_db)):
    text = await fetch_spacetrack_tle_text(timeout=60)
    records = parse_tle(text)
    counts = ingest_tle_records(db, records, source=PUBLIC_SOURCE)

    return {
        "ok": True,
        "source": "space-track gp tle",
        "cache_source": PUBLIC_SOURCE,
        **counts,
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

    l1, l2 = normalize_tle_pair(payload.tle_line1, payload.tle_line2)
    if not (l1 and l2):
        raise HTTPException(status_code=422, detail="Invalid TLE: expected line1 starting with '1 ' and line2 starting with '2 '")
    if not tle_is_propagatable(l1, l2):
        raise HTTPException(status_code=422, detail="Invalid or non-propagatable TLE at current epoch")

    sat = Satellite(
        catalog_number=catalog,
        name=payload.name,
        tle_line1=l1,
        tle_line2=l2,
        source=USER_SOURCE,
        last_updated=datetime.utcnow(),
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
    next_l1 = payload.tle_line1 if payload.tle_line1 is not None else sat.tle_line1
    next_l2 = payload.tle_line2 if payload.tle_line2 is not None else sat.tle_line2
    if payload.tle_line1 is not None or payload.tle_line2 is not None:
        l1, l2 = normalize_tle_pair(next_l1, next_l2)
        if not (l1 and l2):
            raise HTTPException(status_code=422, detail="Invalid TLE: expected line1 starting with '1 ' and line2 starting with '2 '")
        if not tle_is_propagatable(l1, l2):
            raise HTTPException(status_code=422, detail="Invalid or non-propagatable TLE at current epoch")
        sat.tle_line1 = l1
        sat.tle_line2 = l2
    sat.last_updated = datetime.utcnow()

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

    q = select(Satellite).where(Satellite.source == USER_SOURCE)
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
                    "sat1": sat1["name"],
                    "sat2": sat2["name"],
                    "source1": sat1.get("source"),
                    "source2": sat2.get("source"),
                    "satellite1_id": sat1.get("db_id"),
                    "satellite2_id": sat2.get("db_id"),
                    "distance_km": round(dist, 3),
                })
    return collisions

def load_user_tles(db: Session, limit: int):
    """
    Load user satellites from DB and shape like cached TLE rows.
    """
    rows = db.query(Satellite).filter(Satellite.source == USER_SOURCE).limit(limit).all()
    tles = []
    for s in rows:
        shaped = shape_tle_from_satellite(s, USER_SOURCE)
        if shaped:
            tles.append(shaped)
    return tles


def store_collisions(db: Session, timestamp, collisions):
    """
    Save collisions to DB when both satellites come from user DB rows.
    Duplicate = same ordered pair of DB ids + same timestamp.
    """
    saved = 0
    for c in collisions:
        id1 = c.get("satellite1_id")
        id2 = c.get("satellite2_id")
        if id1 is None or id2 is None:
            continue
        if id1 > id2:
            id1, id2 = id2, id1

        exists = db.execute(
            select(CollisionPrediction).where(
                CollisionPrediction.satellite1_id == id1,
                CollisionPrediction.satellite2_id == id2,
                CollisionPrediction.predicted_time == timestamp
            )
        ).scalar_one_or_none()
        if exists:
            continue

        row = CollisionPrediction(
            satellite1_id=id1,
            satellite2_id=id2,
            probability=None,
            distance_km=c["distance_km"],
            predicted_time=timestamp
        )
        db.add(row)
        saved += 1

    db.commit()
    return saved


@app.get("/api/collisions")
async def api_collisions(
    limit: int = Query(300, ge=10, le=2000, description="How many satellites to check"),
    threshold_km: float = Query(1.0, ge=0.01, le=50.0, description="Collision distance threshold (km)"),
    db: Session = Depends(get_db)
):
    """
    Combine user and cached public satellites, compute collisions,
    save unique results, and return them cleanly.
    """
    # 1) user satellites
    user_tles = load_user_tles(db, limit)

    # 2) cached public satellites
    public_tles = load_cached_public_tles(db, limit)
    if not user_tles and not public_tles:
        raise_empty_public_cache()

    # 3) merge
    all_tles = user_tles + public_tles

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
                "source": row["source"],
                "db_id": row.get("db_id"),
            })
        except Exception:
            continue

    # 5) reuse existing compute_collisions
    collisions = compute_collisions(positions, threshold_km)

    # 6) save to DB
    saved_count = store_collisions(db, now, collisions)

    # 7) clean, readable return
    result = {
        "timestamp": now.isoformat(),
        "threshold_km": threshold_km,
        "total_checked": len(positions),
        "collision_count": len(collisions),
        "saved_to_db": saved_count,
        "collisions": []
    }

    for c in collisions:
        result["collisions"].append({
            "satellite1_label": c["sat1"],
            "satellite2_label": c["sat2"],
            "source1": c["source1"],
            "source2": c["source2"],
            "distance_km": c["distance_km"],
            "predicted_time": now.isoformat(),
        })

    return result




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

