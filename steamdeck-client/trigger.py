"""Send unlock trigger to the PC agent."""

from __future__ import annotations

import hashlib
import hmac
import logging
import socket
import threading
import time
from socket import AF_INET, SOCK_DGRAM

from config import Config

logger = logging.getLogger(__name__)

UNLOCK_WAIT_SECONDS = 5


class TriggerError(Exception):
    """Raised when the unlock trigger fails to send."""


def send_unlock(config: Config, cancel: threading.Event) -> None:
    """Send UDP unlock packet to the PC agent.

    Returns immediately if cancel is set.
    Raises TriggerError on network failure.
    """
    if cancel.is_set():
        logger.debug("Unlock trigger cancelled before sending")
        return

    timestamp = int(time.time())

    if config.agent_secret:
        base = f"unlock:{timestamp}"
        mac = hmac.new(
            config.agent_secret.encode(),
            base.encode(),
            hashlib.sha256,
        ).hexdigest()
        payload = f"{base}:{mac}"
    else:
        payload = f"unlock:{timestamp}"

    encoded = payload.encode()
    logger.info(
        "Sending unlock trigger to %s:%d",
        config.pc_ip,
        config.agent_port,
    )

    try:
        with socket.socket(AF_INET, SOCK_DGRAM) as sock:
            sock.sendto(encoded, (config.pc_ip, config.agent_port))
    except OSError as exc:
        raise TriggerError(f"Failed to send unlock trigger: {exc}") from exc

    cancel.wait(UNLOCK_WAIT_SECONDS)
