"""One place that decides where user state (ledger, config) lives.

Default: ~/.two-sleeve — stable no matter which directory you run the CLI
from, so there is exactly one journal and one config. Override with the
TWO_SLEEVE_DATA_DIR environment variable (e.g. set it to ./data to keep
state inside a repo checkout). Commands that read state print the path
they used, so a surprisingly-empty report is always diagnosable.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("TWO_SLEEVE_DATA_DIR", str(Path.home() / ".two-sleeve")))
