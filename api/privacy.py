def is_session_listing_enabled(branding_config):
    """Return whether the tenant allows public session listing."""
    privacy = branding_config.get("privacy")
    if not isinstance(privacy, dict):
        return True

    allow_session_listing = privacy.get("allowSessionListing")
    if allow_session_listing is not None:
        return bool(allow_session_listing)

    if privacy.get("privateFirst") is True:
        return False

    return True
