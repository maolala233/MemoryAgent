"""Verify that all core mandol modules can be imported without errors."""


def test_src_imports():
    """Test that key public classes are importable from their packages."""
    from Mandol.src.mandol.application import SemanticGraphService, SemanticMapService
    from Mandol.src.mandol.domain import MemorySpace, MemoryUnit
    from Mandol.src.mandol.infrastructure import InMemoryGraphStore, InMemoryUnitStore
    from Mandol.src.mandol.ports import StaticEmbeddingProvider

    assert SemanticMapService
    assert SemanticGraphService
    assert MemoryUnit
    assert MemorySpace
    assert InMemoryUnitStore
    assert InMemoryGraphStore
    assert StaticEmbeddingProvider
