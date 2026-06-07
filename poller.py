"""Poll until a remote host comes online."""

from __future__ import annotations

import logging
import socket
import threading
import time

from config import Config

logger = logging.getLogger(__name__)


class PollTimeoutError(Exception):
    """Raised when the host does not come online within the timeout."""


def poll_until_online(config: Config, cancel: threading.Event) -> None:
    """Poll via TCP until the target PC is online.

    Raises PollTimeoutError if the deadline is exceeded.
    Returns immediately if cancel is set.
    """
    deadline = time.monotonic() + config.poll_timeout_seconds
    logger.info(
        "Polling %s:%d with timeout %ds",
        config.pc_ip,
        config.poll_tcp_port,
        config.poll_timeout_seconds,
    )

    while True:
        if cancel.is_set():
            logger.debug("Polling cancelled")
            return

        if time.monotonic() >= deadline:
            raise PollTimeoutError(
                f"Host {config.pc_ip} did not come online within "
                f"{config.poll_timeout_seconds} seconds"
            )

        try:
            with socket.create_connection((config.pc_ip, config.poll_tcp_port), timeout=2):
                logger.info("Host %s is online", config.pc_ip)
                return
        except OSError:
            logger.debug("Host not yet online, waiting %ds", config.poll_interval_seconds)
            cancel.wait(config.poll_interval_seconds)
