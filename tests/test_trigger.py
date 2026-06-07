"""Tests for trigger.py."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

import trigger
from config import Config
from trigger import TriggerError, send_unlock


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


def test_send_unlock_no_secret(mocker):
    """send_unlock sends correct plain payload when no secret is set."""
    mock_socket_instance = MagicMock()
    mock_socket_cm = MagicMock()
    mock_socket_cm.__enter__ = MagicMock(return_value=mock_socket_instance)
    mock_socket_cm.__exit__ = MagicMock(return_value=False)
    mocker.patch("trigger.socket.socket", return_value=mock_socket_cm)
    mocker.patch("trigger.time.time", return_value=1000000)

    cfg = make_config()
    cancel = threading.Event()
    mocker.patch.object(cancel, "wait")

    send_unlock(cfg, cancel)

    mock_socket_instance.sendto.assert_called_once()
    payload, addr = mock_socket_instance.sendto.call_args[0]
    assert payload.startswith(b"unlock:1000000")
    assert addr == (cfg.pc_ip, cfg.agent_port)


def test_send_unlock_with_secret(mocker):
    """send_unlock sends HMAC-signed payload when secret is set."""
    mock_socket_instance = MagicMock()
    mock_socket_cm = MagicMock()
    mock_socket_cm.__enter__ = MagicMock(return_value=mock_socket_instance)
    mock_socket_cm.__exit__ = MagicMock(return_value=False)
    mocker.patch("trigger.socket.socket", return_value=mock_socket_cm)
    mocker.patch("trigger.time.time", return_value=1000000)

    cfg = make_config(agent_secret="mysecret")
    cancel = threading.Event()
    mocker.patch.object(cancel, "wait")

    send_unlock(cfg, cancel)

    mock_socket_instance.sendto.assert_called_once()
    payload, addr = mock_socket_instance.sendto.call_args[0]
    decoded = payload.decode()
    parts = decoded.split(":")
    assert len(parts) == 3, f"Expected 3 colon-separated parts, got: {decoded!r}"
    assert parts[0] == "unlock"
    assert parts[1] == "1000000"
    assert len(parts[2]) == 64, f"Expected 64-char hex HMAC, got len {len(parts[2])}"


def test_send_unlock_cancelled(mocker):
    """send_unlock returns without sending if cancel is already set."""
    mock_socket_cls = mocker.patch("trigger.socket.socket")

    cfg = make_config()
    cancel = threading.Event()
    cancel.set()

    send_unlock(cfg, cancel)

    mock_socket_cls.assert_not_called()


def test_send_unlock_os_error(mocker):
    """send_unlock wraps OSError in TriggerError."""
    mock_socket_instance = MagicMock()
    mock_socket_instance.sendto.side_effect = OSError("network error")
    mock_socket_cm = MagicMock()
    mock_socket_cm.__enter__ = MagicMock(return_value=mock_socket_instance)
    mock_socket_cm.__exit__ = MagicMock(return_value=False)
    mocker.patch("trigger.socket.socket", return_value=mock_socket_cm)
    mocker.patch("trigger.time.time", return_value=1000000)

    cfg = make_config()
    cancel = threading.Event()

    with pytest.raises(TriggerError):
        send_unlock(cfg, cancel)
