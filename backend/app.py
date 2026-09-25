"""
VitalBand Backend Launcher (FastAPI Wrapper for Backwards Compatibility)
"""

import uvicorn

if __name__ == "__main__":
    print("Launching VitalBand Production Backend (FastAPI)...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=5000, reload=True)
