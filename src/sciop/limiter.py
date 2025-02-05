from slowapi import Limiter
from slowapi.util import get_remote_address

sciop_limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    default_limits=["10 per minute", "100 per hour", "1000 per day"],
)
