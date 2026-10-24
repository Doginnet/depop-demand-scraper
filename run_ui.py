import sys
from pathlib import Path

# Add src to python path for direct script execution
sys.path.insert(0, str(Path(__file__).parent / "src"))

from depop.ui import start

if __name__ == "__main__":
    start()
