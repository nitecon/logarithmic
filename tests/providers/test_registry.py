"""Tests for the provider registry."""

import pytest
from unittest.mock import Mock

from logarithmic.providers.registry import ProviderRegistry
from logarithmic.providers.base import LogProvider


def test_registry_singleton() -> None:
    """Test that registry returns the same instance."""
    registry1 = ProviderRegistry.get_instance()
    registry2 = ProviderRegistry.get_instance()
    
    assert registry1 is registry2


def test_register_provider() -> None:
    """Test registering a provider."""
    registry = ProviderRegistry.get_instance()
    mock_provider = Mock(spec=LogProvider)
    
    registry.register("test_provider", mock_provider)
    
    assert registry.get_provider("test_provider") is mock_provider


def test_get_nonexistent_provider() -> None:
    """Test getting a provider that doesn't exist."""
    registry = ProviderRegistry.get_instance()
    
    assert registry.get_provider("nonexistent") is None


def test_unregister_provider() -> None:
    """Test unregistering a provider."""
    registry = ProviderRegistry.get_instance()
    mock_provider = Mock(spec=LogProvider)
    
    registry.register("test_provider", mock_provider)
    registry.unregister("test_provider")
    
    assert registry.get_provider("test_provider") is None


def test_list_providers() -> None:
    """Test listing all registered providers."""
    registry = ProviderRegistry.get_instance()
    
    # Clear registry first
    for name in list(registry.list_providers()):
        registry.unregister(name)
    
    mock_provider1 = Mock(spec=LogProvider)
    mock_provider2 = Mock(spec=LogProvider)
    
    registry.register("provider1", mock_provider1)
    registry.register("provider2", mock_provider2)
    
    providers = registry.list_providers()
    assert "provider1" in providers
    assert "provider2" in providers
    assert len(providers) >= 2
