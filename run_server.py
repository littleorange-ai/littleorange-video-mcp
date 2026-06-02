import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from video_ai_mcp.server import main

if __name__ == "__main__":
    main()
