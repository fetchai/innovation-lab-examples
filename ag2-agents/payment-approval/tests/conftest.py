"""
Ensure payment-approval/ is on sys.path so local modules are importable.
"""

import asyncio
import os
import sys

import pytest

parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent not in sys.path:
    sys.path.insert(0, parent)


@pytest.fixture(autouse=True)
def ensure_event_loop():
    """Keep a usable event loop available for the synchronous tests.

    pytest-asyncio closes and unsets the loop after each async test, but
    SingleA2AAdapter calls asyncio.get_event_loop() during construction, so the
    sync tests that build an adapter fail if they run after an async test.
    """
    try:
        asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield
