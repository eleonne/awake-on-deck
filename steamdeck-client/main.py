"""Entry point for Awake on Deck — Steam Deck client."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".local" / "share" / "steamdeck-client"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "steamdeck-client.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        from ui.app import App

        App().run()
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
