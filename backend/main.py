import logging
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.config import BASE_DIR
from backend.database import engine, Base, ensure_database_indexes, get_db
import backend.models  # ensure models are registered
from backend.analytics.anomaly_detector import run_hybrid_anomaly_detection
from backend.analytics.recommendation_engine import generate_and_sync_recommendations

# Import API Routers
from backend.api.routes_plants import router as plants_router
from backend.api.routes_energy import router as energy_router
from backend.api.routes_production import router as production_router
from backend.api.routes_anomalies import router as anomalies_router
from backend.api.routes_recommendations import router as recommendations_router
from backend.api.routes_maintenance import router as maintenance_router
from backend.api.routes_data_quality import router as data_quality_router
from backend.api.routes_admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("energyiq.main")

app = FastAPI(
    title="EnergyIQ – AI-Powered Industrial Energy Intelligence Platform",
    description="End-to-End Industrial Energy Intelligence, Anomaly Detection & Decision Optimization",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers Mount
app.include_router(plants_router, prefix="/api")
app.include_router(energy_router, prefix="/api")
app.include_router(production_router, prefix="/api")
app.include_router(anomalies_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(maintenance_router, prefix="/api")
app.include_router(data_quality_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/api/health")
def healthcheck():
    return {
        "status": "HEALTHY",
        "service": "EnergyIQ Core API",
        "version": "1.0.0",
        "database": "SQLite / PostgreSQL Compatible"
    }


# Frontend static files mounting
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    def serve_dashboard():
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "EnergyIQ API operational. Frontend index.html not yet built."}


@app.on_event("startup")
def on_startup():
    logger.info("Initializing EnergyIQ database and tables...")
    Base.metadata.create_all(bind=engine)
    ensure_database_indexes()

    # Pre-populate anomalies and recommendations if tables are empty
    with Session(engine) as db:
        try:
            anom_count = db.query(backend.models.AnomalyRecord).count()
            if anom_count == 0:
                logger.info("Running initial hybrid anomaly detection...")
                run_hybrid_anomaly_detection(db, "PLANT-001")

            rec_count = db.query(backend.models.Recommendation).count()
            if rec_count == 0:
                logger.info("Generating initial recommendations...")
                generate_and_sync_recommendations(db, "PLANT-001")
        except Exception as e:
            logger.warning(f"Startup initialization notice: {e}")

    logger.info("EnergyIQ application startup complete. Ready for telemetry ingestion and user traffic.")

