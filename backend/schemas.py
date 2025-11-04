from pydantic import BaseModel
from datetime import datetime
from typing import List
class SatelliteOut(BaseModel):
    id: int
    catalog_number:int | None = None
    name:str |None = None
    tle_line1: str | None = None
    tle_line2: str | None = None
    last_updated: datetime | None = None

    class Config:
        from_attributes = True

class CollisionOut(BaseModel):
    satellite1_id: int | None = None
    satellite2_id: int | None = None
    satellite1_label: str
    satellite2_label: str
    distance_km: float
    predicted_time: datetime

    source1: str
    source2: str