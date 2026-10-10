"""Tests for poller.py."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

import poller
from config import Config
from poller import PollTimeoutError, poll_until_online


def make_config(**kwargs) -> Config:
    defaults = {
        "pc_mac": "AA:BB:CC:DD:EE:FF",
        "pc_ip": "192.168.1.100",
        "wol_broadcast": "192.168.1.255",
        "wol_port": 9,
        "poll_timeout_seconds": 5,
        "poll_interval_seconds": 1,
        "poll_tcp_port": 445,
    }
    defaults.update(kwargs)
    return Config(**defaults)


def test_poll_success(mocker):
    """poll_until_online returns without exception when connection succeeds."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock())
    cm.__exit__ = MagicMock(return_value=False)
    mocker.patch("poller.socket.create_connection", return_value=cm)
    mocker.patch("poller.time.monotonic", return_value=0)

    cfg = make_config()
    cancel = threading.Event()

    # Should not raise
    poll_until_online(cfg, cancel)


def test_poll_timeout(mocker):
    """poll_until_online raises PollTimeoutError when deadline is exceeded."""
    mocker.patch("poller.socket.create_connection", side_effect=OSError("refused"))
    mocker.patch("poller.time.monotonic", side_effect=[0, 1, 10])

    cfg = make_config(poll_timeout_seconds=5, poll_interval_seconds=1)
    cancel = threading.Event()
    mocker.patch.object(cancel, "wait")

    with pytest.raises(PollTimeoutError):
        poll_until_online(cfg, cancel)


def test_poll_cancelled(mocker):
    """poll_until_online returns without attempting connection if cancel is set."""
    mock_connect = mocker.patch("poller.socket.create_connection")
    mocker.patch("poller.time.monotonic", return_value=0)

    cfg = make_config()
    cancel = threading.Event()
    cancel.set()

    poll_until_online(cfg, cancel)

    mock_connect.assert_not_called()
