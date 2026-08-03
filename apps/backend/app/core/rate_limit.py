"""
PrintBar Backend — Rate Limiting
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Default rate limiter using client IP
# For production we might configure this to use Redis, but slowapi's default
# memory backend works identically for the API interface.
limiter = Limiter(key_func=get_remote_address)
