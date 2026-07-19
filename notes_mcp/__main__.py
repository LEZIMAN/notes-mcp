"""让 `python -m notes_mcp ...` 调用 cli.main。"""

import sys

from notes_mcp.cli import main

if __name__ == "__main__":
    sys.exit(main())
