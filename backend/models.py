from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import datetime

Base = declarative_base()

class Satellite(Base):
    __tablename__ = "satellites"
    id = Column(Integer, primary_key=True, index = True)
    catalog_number = Column(Integer, unique=True, index=True)
    name = Column(String, index=True)
    tle_line1 = Column(Text)  # First line of TLE data
    tle_line2 = Column(Text)  # Second line of TLE data
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class CollisionPrediction(Base):
    __tablename__ = "collision_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    satellite1_id = Column(Integer)
    satellite2_id = Column(Integer)
    probability = Column(Float)
    predicted_time = Column(DateTime)
    distance_km = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)