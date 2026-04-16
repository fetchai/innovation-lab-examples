"""Tests for orchestrator.storage – pairing store."""

from orchestrator.storage import PairingStore


def test_pair_and_lookup():
    store = PairingStore()
    rec = store.pair("u_1", "dev_1", "aa" * 32)
    assert rec.user_id == "u_1"
    assert store.is_paired("u_1", "dev_1") is True
    assert store.get("u_1", "dev_1") is not None


def test_unpair():
    store = PairingStore()
    store.pair("u_1", "dev_1", "bb" * 32)
    assert store.unpair("u_1", "dev_1") is True
    assert store.is_paired("u_1", "dev_1") is False


def test_unpair_nonexistent():
    store = PairingStore()
    assert store.unpair("u_1", "dev_1") is False


def test_devices_for_user():
    store = PairingStore()
    store.pair("u_1", "dev_1", "aa" * 32)
    store.pair("u_1", "dev_2", "bb" * 32)
    store.pair("u_2", "dev_3", "cc" * 32)
    assert len(store.devices_for_user("u_1")) == 2
    assert len(store.devices_for_user("u_2")) == 1
    assert len(store.devices_for_user("u_3")) == 0


def test_all_devices():
    store = PairingStore()
    store.pair("u_1", "dev_1", "aa" * 32)
    store.pair("u_2", "dev_2", "bb" * 32)
    assert len(store.all_devices()) == 2
