import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure current directory is in sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.chdir(project_root)
    
    print("[INFO] Starting Academic Intelligent Hub Backend on http://localhost:8000")
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)
