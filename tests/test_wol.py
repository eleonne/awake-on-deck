"""Tests for wol.py."""

from __future__ import annotations

import threading

import pytest

import wol
from config import Config
from wol import WoLError, send_wol


def make_config(**kwargs) -> Config:
    defaults = {
        "pc_mac": "AA:BB:CC:DD:EE:FF",
        "pc_ip": "192.168.1.100",
        "wol_broadcast": "192.168.1.255",
        "wol_port": 9,
        "agent_port": 9876,
        "agent_secret": "",
        "poll_timeout_seconds": 90,
        "poll_interval_seconds": 3,
        "poll_tcp_port": 445,
    }
    defaults.update(kwargs)
    return Config(**defaults)


def test_send_wol_success(mocker):
    """send_wol calls send_magic_packet with correct arguments."""
    mock_send = mocker.patch("wol.wakeonlan.send_magic_packet")
    cfg = make_config()
    cancel = threading.Event()

    send_wol(cfg, cancel)

    mock_send.assert_called_once_with(
        cfg.pc_mac,
        ip_address=cfg.wol_broadcast,
        port=cfg.wol_port,
    )


def test_send_wol_cancelled(mocker):
    """send_wol returns without sending if cancel is already set."""
    mock_send = mocker.patch("wol.wakeonlan.send_magic_packet")
    cfg = make_config()
    cancel = threading.Event()
    cancel.set()

    send_wol(cfg, cancel)

    mock_send.assert_not_called()


def test_send_wol_raises_wol_error(mocker):
    """send_wol wraps OSError in WoLError."""
    mocker.patch("wol.wakeonlan.send_magic_packet", side_effect=OSError("network error"))
    cfg = make_config()
    cancel = threading.Event()

    with pytest.raises(WoLError):
        send_wol(cfg, cancel)
