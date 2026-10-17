"""Every page renders without an exception (Streamlit AppTest) and shows the mode banner."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))   # pages import `ui` and `components` from the app folder
PAGES = ["main.py"] + [f"pages/{p.name}" for p in sorted((APP / "pages").glob("*.py"))]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Replay mode" in i.value for i in at.info)
