"""
agents/gemini_llm.py
====================
Timeout HTTP unificado para ChatGoogleGenerativeAI (Sprint 33).

Evita que llamadas a Gemini queden colgadas indefinidamente si la red
o el servicio no responden. Se pasa como ``request_timeout`` (segundos).
"""

from __future__ import annotations

GEMINI_REQUEST_TIMEOUT_SEC: float = 30.0
