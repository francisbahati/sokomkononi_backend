import hashlib
from django.core.cache import cache

MAX_FAILS = 5        # kwa (identifier + IP)
MAX_IP_FAILS = 20    # kwa IP peke yake
WINDOW = 15 * 60     # sekunde


def _key(kind, value):
    h = hashlib.sha256(str(value).strip().lower().encode()).hexdigest()[:32]
    return f"login_fail:{kind}:{h}"


def _keys(identifier, ip):
    return _key("id", f"{identifier}|{ip}"), _key("ip", ip)


def is_locked(identifier, ip):
    id_key, ip_key = _keys(identifier, ip)
    return (cache.get(id_key, 0) >= MAX_FAILS
            or cache.get(ip_key, 0) >= MAX_IP_FAILS)


def register_failure(identifier, ip):
    for key in _keys(identifier, ip):
        cache.add(key, 0, WINDOW)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, WINDOW)


def clear_failures(identifier, ip):
    cache.delete(_keys(identifier, ip)[0])