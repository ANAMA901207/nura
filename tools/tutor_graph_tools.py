"""
tools/tutor_graph_tools.py
===========================
Lista central de tools LangGraph usadas por `tutor_agent` con `bind_tools` (Sprint 33).
"""

from __future__ import annotations

from tools.concept_lookup_tool import lookup_concepts
from tools.diagram_tool import generate_diagram
from tools.hierarchy_tool import lookup_hierarchy
from tools.web_search_tool import web_search

TUTOR_BIND_TOOLS = [
    web_search,
    generate_diagram,
    lookup_hierarchy,
    lookup_concepts,
]
