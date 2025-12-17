"""Gmail Integration Services."""

# Lazy imports to avoid circular dependencies and heavy imports during testing

__all__ = [
    "GmailOAuthManager",
    "GmailClient",
    "GmailHistorySync",
    "GmailPushNotifications",
    "EmailDocumentProcessor",
]


def __getattr__(name):
    """Lazy import services to avoid heavy dependencies."""
    if name == "GmailOAuthManager":
        from services.email.oauth_manager import GmailOAuthManager
        return GmailOAuthManager
    elif name == "GmailClient":
        from services.email.gmail_client import GmailClient
        return GmailClient
    elif name == "GmailHistorySync":
        from services.email.history_sync import GmailHistorySync
        return GmailHistorySync
    elif name == "GmailPushNotifications":
        from services.email.push_notifications import GmailPushNotifications
        return GmailPushNotifications
    elif name == "EmailDocumentProcessor":
        from services.email.document_integration import EmailDocumentProcessor
        return EmailDocumentProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
