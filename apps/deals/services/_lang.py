# apps/deals/services/_lang.py

def user_lang(user):
    """Rudisha lugha ya mtumiaji kutoka UserPreferences."""
    if not user:
        return "sw"
    prefs = getattr(user, "preferences", None)
    if prefs is None:
        return "sw"
    return getattr(prefs, "language", None) or "sw"