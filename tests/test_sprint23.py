"""
tests/test_sprint23.py
======================
Harness para Sprint 23 — Fix sesión que expira.

Verifica que:
- is_session_valid() retorna True cuando hay user_id y expiry futuro.
- is_session_valid() retorna False cuando la sesión expiró.
- is_session_valid() retorna False sin sesión.
- refresh_session() actualiza session_expiry a un valor mayor.
- El logout (limpiar session_state) elimina user_id de la sesión.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch


# ── helpers de mock ───────────────────────────────────────────────────────────

def _make_session_state(data: dict) -> MagicMock:
    """
    Crea un MagicMock que se comporta como st.session_state.

    Soporta .get(key, default=None), acceso por [] y 'key in obj'.
    """
    mock = MagicMock()
    store = dict(data)

    mock.get.side_effect = lambda k, default=None: store.get(k, default)
    mock.__getitem__ = lambda self, k: store[k]
    mock.__setitem__ = lambda self, k, v: store.__setitem__(k, v)
    mock.__contains__ = lambda self, k: k in store
    mock.__delitem__ = lambda self, k: store.__delitem__(k)
    mock.keys.side_effect = lambda: list(store.keys())
    # Para que el refresh pueda actualizar session_expiry en el mismo store
    mock._store = store

    return mock


def _patch_st(session_data: dict):
    """Context manager que parchea streamlit.session_state con session_data."""
    import sys
    st_mock = MagicMock()
    state_mock = _make_session_state(session_data)
    st_mock.session_state = state_mock
    return patch.dict(sys.modules, {"streamlit": st_mock}), st_mock, state_mock


# ── tests ─────────────────────────────────────────────────────────────────────

def test_session_persists_after_rerun():
    """
    session_state con user_id válido y expiry futuro → is_session_valid() = True.

    Simula un rerun de Streamlit en el que session_state conserva los valores
    guardados en el login anterior.
    """
    future_expiry = time.time() + 1800   # 30 min en el futuro

    ctx, st_mock, state = _patch_st({
        "user_id":        42,
        "username":       "ana",
        "session_expiry": future_expiry,
    })

    with ctx:
        import importlib
        import ui.auth as auth_module
        importlib.reload(auth_module)
        result = auth_module.is_session_valid()

    assert result is True, "La sesión activa debe ser válida tras el rerun"


def test_expired_session_returns_false():
    """
    session_state con expiry en el pasado → is_session_valid() = False.
    """
    past_expiry = time.time() - 10   # ya expiró

    ctx, st_mock, state = _patch_st({
        "user_id":        42,
        "session_expiry": past_expiry,
    })

    with ctx:
        import importlib
        import ui.auth as auth_module
        importlib.reload(auth_module)
        result = auth_module.is_session_valid()

    assert result is False, "Una sesión con expiry en el pasado no debe ser válida"


def test_no_session_returns_false():
    """
    session_state vacío (sin user_id ni session_expiry) → is_session_valid() = False.
    """
    ctx, st_mock, state = _patch_st({})

    with ctx:
        import importlib
        import ui.auth as auth_module
        importlib.reload(auth_module)
        result = auth_module.is_session_valid()

    assert result is False, "Sin sesión activa, is_session_valid debe retornar False"


def test_refresh_updates_expiry():
    """
    refresh_session() actualiza session_expiry a un valor mayor cuando
    la sesión está próxima a expirar (quedan < 5 minutos).
    """
    near_expiry = time.time() + 60   # quedan solo 60 s → debe renovar

    session_data = {
        "user_id":        42,
        "session_expiry": near_expiry,
    }
    ctx, st_mock, state = _patch_st(session_data)

    with ctx:
        import importlib
        import ui.auth as auth_module
        importlib.reload(auth_module)
        refreshed = auth_module.refresh_session()
        new_expiry = state._store.get("session_expiry")

    assert refreshed is True, "refresh_session() debe retornar True cuando renueva"
    assert new_expiry > near_expiry, (
        f"session_expiry debe aumentar tras el refresh: {new_expiry} > {near_expiry}"
    )
    assert new_expiry > time.time() + 3000, (
        "La nueva expiración debe ser al menos ~50 min en el futuro"
    )


def test_logout_clears_session():
    """
    Después del logout (limpiar session_state), user_id no debe estar presente
    y is_session_valid() debe retornar False.

    Simula el bloque de logout de app.py:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    """
    future_expiry = time.time() + 1800

    session_data = {
        "user":           object(),
        "user_id":        42,
        "username":       "ana",
        "session_expiry": future_expiry,
    }
    ctx, st_mock, state = _patch_st(session_data)

    with ctx:
        import importlib
        import ui.auth as auth_module
        importlib.reload(auth_module)

        # Simular logout: borrar todas las claves del session_state
        for key in list(state._store.keys()):
            del state._store[key]

        result = auth_module.is_session_valid()

    assert result is False, "Tras el logout, is_session_valid debe retornar False"
    assert "user_id" not in state._store, "user_id debe haberse eliminado en el logout"
