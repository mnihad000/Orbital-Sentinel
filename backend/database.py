from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from models import Base

# SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./orbital_sentinel.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

def ensure_schema():
    inspector = inspect(engine)
    if "satellites" not in inspector.get_table_names():
        return

    existing_columns = {c["name"] for c in inspector.get_columns("satellites")}
    with engine.begin() as conn:
        if "source" not in existing_columns:
            conn.execute(text("ALTER TABLE satellites ADD COLUMN source VARCHAR DEFAULT 'user'"))
        conn.execute(
            text("UPDATE satellites SET source = 'user' WHERE source IS NULL OR source = ''")
        )

ensure_schema()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
