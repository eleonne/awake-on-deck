"""Wake-on-LAN functionality."""

from __future__ import annotations

import logging
import threading

import wakeonlan

from config import Config

logger = logging.getLogger(__name__)


class WoLError(Exception):
    """Raised when a Wake-on-LAN packet fails to send."""


def send_wol(config: Config, cancel: threading.Event) -> None:
    """Send a Wake-on-LAN magic packet.

    Returns immediately if cancel is set.
    Raises WoLError on network failure.
    """
    if cancel.is_set():
        logger.debug("WoL cancelled before sending")
        return

    logger.info(
        "Sending WoL magic packet to %s via broadcast %s:%d",
        config.pc_mac,
        config.wol_broadcast,
        config.wol_port,
    )
    try:
        wakeonlan.send_magic_packet(
            config.pc_mac,
            ip_address=config.wol_broadcast,
            port=config.wol_port,
        )
    except OSError as exc:
        raise WoLError(f"Failed to send WoL packet: {exc}") from exc
