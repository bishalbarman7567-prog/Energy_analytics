import os
import sys

pkg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "energy_analytics")
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

import uvicorn

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

