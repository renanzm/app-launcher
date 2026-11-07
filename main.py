"""Entry point used by PyInstaller (equivalent to `python -m launcher`)."""

import sys

from launcher.app import main

if __name__ == "__main__":
    sys.exit(main())
