import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import DATABASE_URL, DB_PATH

logger = logging.getLogger("energyiq.database")

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_indexes():
    """Ensure high-performance indexes exist on critical tables for millisecond API queries."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_reading_meter ON EnergyReading (meter_id);",
        "CREATE INDEX IF NOT EXISTS idx_reading_machine ON EnergyReading (machine_id);",
        "CREATE INDEX IF NOT EXISTS idx_reading_start_ts ON EnergyReading (interval_start_ts);",
        "CREATE INDEX IF NOT EXISTS idx_reading_quality ON EnergyReading (quality_flag);",
        "CREATE INDEX IF NOT EXISTS idx_reading_batch ON EnergyReading (batch_id);",
        "CREATE INDEX IF NOT EXISTS idx_batch_machine ON ProductionBatch (machine_id);",
        "CREATE INDEX IF NOT EXISTS idx_batch_shift ON ProductionBatch (shift_id);",
        "CREATE INDEX IF NOT EXISTS idx_weather_ts ON WeatherObservation (timestamp_local);",
    ]
    with engine.connect() as conn:
        for stmt in index_statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Index execution warning ({stmt}): {e}")
        conn.commit()
    logger.info("Database performance indexes verified.")


def init_db():
    import backend.models  # noqa
    Base.metadata.create_all(bind=engine)
    ensure_database_indexes()

init_db()
