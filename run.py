"""
Root runner script to launch the Website Archive Submitter application.
Usage:
    python run.py
"""
import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print("=================================================================")
    print("  Website Archive Submitter & Automated Backup Repository")
    print(f"  Starting server at http://{host}:{port}")
    print("=================================================================")
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
