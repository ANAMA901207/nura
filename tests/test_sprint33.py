"""Sprint 33 — harness: tools formales LangGraph del tutor."""
from __future__ import annotations

from pathlib import Path


def test_tools_folder_exists():
    root = Path(__file__).resolve().parent.parent
    assert (root / "tools").is_dir()
    assert (root / "tools" / "__init__.py").exists()


def test_web_search_tool_is_tool():
    from tools.web_search_tool import web_search

    assert hasattr(web_search, "name")
    assert isinstance(web_search.name, str)
    assert web_search.name == "web_search"


def test_diagram_tool_is_tool():
    from tools.diagram_tool import generate_diagram

    assert hasattr(generate_diagram, "name")
    assert isinstance(generate_diagram.name, str)
    assert generate_diagram.name == "generate_diagram"


def test_hierarchy_tool_is_tool():
    from tools.hierarchy_tool import lookup_hierarchy

    assert hasattr(lookup_hierarchy, "name")
    assert isinstance(lookup_hierarchy.name, str)
    assert lookup_hierarchy.name == "lookup_hierarchy"


def test_concept_lookup_tool_is_tool():
    from tools.concept_lookup_tool import lookup_concepts

    assert hasattr(lookup_concepts, "name")
    assert isinstance(lookup_concepts.name, str)
    assert lookup_concepts.name == "lookup_concepts"


def test_all_tools_have_docstring():
    from tools.tutor_graph_tools import TUTOR_BIND_TOOLS

    for t in TUTOR_BIND_TOOLS:
        desc = getattr(t, "description", None) or ""
        assert isinstance(desc, str) and desc.strip(), (
            f"tool {getattr(t, 'name', '?')} debe tener description no vacía"
        )


def test_tutor_has_tools_bound():
    from tools.tutor_graph_tools import TUTOR_BIND_TOOLS

    assert len(TUTOR_BIND_TOOLS) == 4
    names = {t.name for t in TUTOR_BIND_TOOLS}
    assert names == {
        "web_search",
        "generate_diagram",
        "lookup_hierarchy",
        "lookup_concepts",
    }


def test_tutor_graph_builds_without_error():
    from agents.graph import build_graph

    graph = build_graph()
    assert graph is not None
