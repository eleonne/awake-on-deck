"""Configuration management for steamdeck-client."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "steamdeck-client"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    pc_mac: str = "AF-AF-AF-AF-AF-AF"
    pc_ip: str = "192.168.1.1"
    wol_broadcast: str = "192.168.1.255"
    wol_port: int = 9
    poll_timeout_seconds: int = 90
    poll_interval_seconds: int = 3
    poll_tcp_port: int = 445


def load_config() -> Config:
    """Read config from file, creating with defaults if missing."""
    if not CONFIG_FILE.exists():
        logger.info("Config file not found, creating with defaults at %s", CONFIG_FILE)
        cfg = Config()
        save_config(cfg)
        return cfg

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})
        logger.debug("Loaded config from %s", CONFIG_FILE)
        return cfg
    except Exception:
        logger.exception("Failed to load config, using defaults")
        return Config()


def save_config(cfg: Config) -> None:
    """Write config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)
    logger.debug("Saved config to %s", CONFIG_FILE)
