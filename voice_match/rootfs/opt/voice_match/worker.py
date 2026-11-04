"""Private CPU inference process, without the Supervisor credential."""

import logging
import sys

from launcher import PrivateLogs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for handler in logging.getLogger().handlers:
    handler.addFilter(PrivateLogs())
sys.path.insert(0, "/app")
from proxy import run

run()
