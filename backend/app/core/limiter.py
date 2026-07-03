"""Shared rate-limiter instance.

Import this module (not app.main) in route files to apply @limiter.limit()
decorators without creating circular imports.

In tests, disable rate limiting via the autouse fixture in conftest.py:
    limiter.enabled = False  (before each test)
    limiter.enabled = True   (after each test)
SlowAPI checks self.enabled at request time, so runtime toggling works.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
