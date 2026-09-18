import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory rate limiter (fine for a single-instance deployment; swap the
# storage_uri to a Redis URL if this app is ever run behind a load balancer
# with multiple instances, since in-memory limits don't share state across
# processes).
#
# Disabled only when TESTING=1 (set by tests/conftest.py) - the automated
# test suite legitimately calls login/register far more often per minute
# than a real client would, and that's test infrastructure noise, not
# something the rate limiter should be judging. Real requests always go
# through the real limits below.
limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("TESTING") != "1")
