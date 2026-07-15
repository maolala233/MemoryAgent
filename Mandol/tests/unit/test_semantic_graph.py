"""Unit tests for SemanticGraphService relationships and neighbor queries."""


from Mandol.src.mandol.application import SemanticGraphService, SemanticMapService
from Mandol.src.mandol.domain import MemoryUnit
from Mandol.src.mandol.infrastructure import (
    InMemoryCosineVectorIndex,
    InMemoryGraphStore,
    InMemoryUnitStore,
)
from Mandol.src.mandol.ports import StaticEmbeddingProvider


def test_semantic_graph_relationship_and_neighbors():
    """Test adding a relationship and retrieving explicit neighbors."""
    store = InMemoryUnitStore()
    embedder = StaticEmbeddingProvider(dim=4, fill=1.0)
    index = InMemoryCosineVectorIndex(dim=4)
    sm = SemanticMapService(store=store, index=index, embedder=embedder)

    gs = InMemoryGraphStore()
    g = SemanticGraphService(semantic_map=sm, graph_store=gs)

    u1 = MemoryUnit(uid="u1", raw_data={"text_content": "A"})
    u2 = MemoryUnit(uid="u2", raw_data={"text_content": "B"})
    g.add_unit(u1)
    g.add_unit(u2)

    g.add_relationship("u1", "u2", "friend", weight=1)

    neighbors = g.get_explicit_neighbors(["u1"], rel_type="friend")
    assert [u.uid for u in neighbors] == ["u2"]

    props = g.get_relationship("u1", "u2", "friend")
    assert props == {"weight": 1}
