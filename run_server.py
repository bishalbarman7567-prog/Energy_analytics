import os
import sys
import uvicorn

# Ensure the energy_analytics directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    
    print("=" * 70)
    print("  EnergyIQ – AI-Powered Industrial Energy Intelligence Platform")
    print(f"  * Interactive Dashboard: http://localhost:{port}/")
    print(f"  * REST API & Swagger:     http://localhost:{port}/docs")
    print(f"  * API Healthcheck:        http://localhost:{port}/api/health")
    print("=" * 70)
    
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")

