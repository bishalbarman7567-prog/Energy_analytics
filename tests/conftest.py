import sys, pathlib
# Add project root to PYTHONPATH so imports like `from backend.xxx` work in tests.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

