"""
tests/conftest.py
=================
Configuración global de pytest para la suite de tests de Nura.

Problema que resuelve
---------------------
Varios archivos de test (test_sprint5.py, test_sprint6.py) instalan un
MagicMock() limpio en sys.modules["streamlit"] dentro de sus funciones de
test sin restaurarlo al finalizar.  Como pytest corre los archivos en orden
alfabético (sprint5 → sprint6 → ui), cuando llega test_ui.py el mock de
streamlit activo es el del último sprint que lo tocó — sin columns.return_value
configurado — y col1, col2, col3 = st.columns(3) lanza ValueError.

Solución
--------
El fixture `streamlit_mock` (autouse=True para el módulo test_ui) reinstala
un mock de streamlit correctamente configurado antes de cada test de ese
módulo y lo restaura al finalizar, aislando completamente ese módulo del
estado que puedan dejar otros archivos de test.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

# ── Garantizar modo SQLite durante todos los tests ────────────────────────────
# Si DATABASE_URL está en el entorno (cargada desde .env local o heredada del
# shell), los tests intentarían conectar a PostgreSQL y fallarían sin red.
#
# Solución: establecer DATABASE_URL="" (cadena vacía, falsy) ANTES de que
# cualquier módulo llame a load_dotenv().  python-dotenv con override=False
# (por defecto) no sobreescribe variables ya presentes en el entorno, así
# que DATABASE_URL queda vacía durante toda la suite → get_db_mode() devuelve
# 'sqlite' y nunca se intenta una conexión PostgreSQL.
os.environ["DATABASE_URL"] = ""


def _make_streamlit_mock() -> MagicMock:
    """
    Crea un MagicMock de streamlit con todos los valores que necesita test_ui.

    Configura:
    - columns.return_value: lista de 3 MagicMock, para que la desestructuración
      col1, col2, col3 = st.columns(3) funcione sin importar el argumento.
    - tabs.return_value: lista de 2 MagicMock (Tab 1 y Tab 2).
    - expander: context manager no-op (necesario para bloques with st.expander).

    Devuelve
    --------
    MagicMock configurado para usarse como reemplazo de streamlit.
    """
    mock = MagicMock()
    # columns() devuelve siempre 3 columnas — suficiente para cualquier llamada
    # con 2, 3 o [1,1,1] como argumento
    mock.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock.tabs.return_value = [MagicMock(), MagicMock()]
    mock.expander.return_value.__enter__ = lambda s: s
    mock.expander.return_value.__exit__ = MagicMock(return_value=False)
    return mock


@pytest.fixture(autouse=True)
def streamlit_mock_for_ui_tests(request):
    """
    Fixture autouse que reinstala el mock de streamlit antes de cada test en
    test_ui.py y lo restaura al finalizar.

    Solo actúa cuando el test pertenece al módulo test_ui; para el resto de
    los módulos es un no-op, por lo que no interfiere con test_sprint4/5/6
    que instalan sus propios mocks.

    Yield fixture: la lógica anterior al yield es setup; la posterior es teardown.
    """
    # Solo interviene en tests definidos en test_ui.py
    if request.module.__name__ != "test_ui":
        yield
        return

    # Guarda el mock actual (puede ser el del último sprint que lo tocó)
    previous = sys.modules.get("streamlit")

    # Instala un mock limpio y correctamente configurado
    fresh_mock = _make_streamlit_mock()
    sys.modules["streamlit"] = fresh_mock

    # Necesario: recargar ui.components para que su `import streamlit as st`
    # tome el nuevo mock.  Sin esto, el módulo ya importado guarda una
    # referencia interna al mock anterior.
    import importlib
    try:
        import ui.components as _comp
        importlib.reload(_comp)
    except Exception:
        pass  # si no se puede recargar no es bloqueante

    yield  # el test se ejecuta aquí

    # Restaurar el estado anterior para no afectar otros tests que vengan después
    if previous is not None:
        sys.modules["streamlit"] = previous
    else:
        sys.modules.pop("streamlit", None)
