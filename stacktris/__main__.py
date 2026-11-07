"""Allow running as `python -m stacktris`."""

import sys

from .cli import main

sys.exit(main())
