from roadsense.config import Settings
from roadsense.db.repository import InMemoryRepository, Repository


def get_repository(settings: Settings) -> Repository:
    """Pick the storage backend from configuration.

    Cosmos when COSMOS_ENDPOINT/COSMOS_KEY are set, otherwise in-memory. The
    caller decides whether "in-memory" is acceptable (tests, --dry-run) or an
    error (a real collector run that would silently store nothing).
    """
    if settings.cosmos_configured:
        from roadsense.db.cosmos import CosmosRepository  # import lazily: SDK not needed for tests

        assert settings.cosmos_endpoint and settings.cosmos_key
        return CosmosRepository(
            settings.cosmos_endpoint,
            settings.cosmos_key.get_secret_value(),
            settings.cosmos_database,
        )
    return InMemoryRepository()
