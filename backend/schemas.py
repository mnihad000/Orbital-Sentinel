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