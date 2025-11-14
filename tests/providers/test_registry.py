"""Tests for the provider registry."""


from logarithmic.providers.base import ProviderType
from logarithmic.providers.registry import ProviderRegistry


def test_registry_singleton() -> None:
    """Test that registry returns the same instance."""
    registry1 = ProviderRegistry.get_instance()
    registry2 = ProviderRegistry.get_instance()

    assert registry1 is registry2


def test_registry_has_builtin_providers() -> None:
    """Test that registry has built-in providers registered."""
    registry = ProviderRegistry.get_instance()

    # Should have FILE and KUBERNETES providers registered
    assert registry.is_registered(ProviderType.FILE)
    assert registry.is_registered(ProviderType.KUBERNETES)


def test_get_available_providers() -> None:
    """Test getting list of available providers."""
    registry = ProviderRegistry.get_instance()

    providers = registry.get_available_providers()

    assert len(providers) >= 2  # At least FILE and KUBERNETES
    assert any(p["type"] == "file" for p in providers)
    assert any(p["type"] == "kubernetes" for p in providers)


def test_get_provider_metadata() -> None:
    """Test getting metadata for a provider."""
    registry = ProviderRegistry.get_instance()

    metadata = registry.get_provider_metadata(ProviderType.FILE)

    assert "display_name" in metadata
    assert "description" in metadata
    assert "icon" in metadata


def test_is_registered() -> None:
    """Test checking if a provider is registered."""
    registry = ProviderRegistry.get_instance()

    assert registry.is_registered(ProviderType.FILE) is True
    # KAFKA is not registered by default
    assert registry.is_registered(ProviderType.KAFKA) is False
