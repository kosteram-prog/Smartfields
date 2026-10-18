"""Every page renders without an exception (Streamlit AppTest) and shows the mode banner."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))   # pages import `ui` and `components` from the app folder
PAGES = ["main.py"] + [f"views/{p.name}" for p in sorted((APP / "views").glob("*.py"))]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Replay mode" in i.value for i in at.info)


def test_loss_page_recalculates_without_extracts():
    at = AppTest.from_file(str(APP / "views/6_Loss.py"), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Tyre pressure" in s.label for s in at.slider)
    assert not any("needs the data extracts" in (w.value or "").lower() for w in at.warning)


ROUTED = ["views/3_Today.py", "views/6_Loss.py", "views/1_Farm.py", "views/2_Season.py"]


@pytest.mark.needs_data
def test_router_shares_machine_across_pages():
    """B3/B4: the router renders sections; a machine chosen on Today is the machine on Loss and Farm."""
    at = AppTest.from_file(str(APP / "main.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    at.switch_page("views/3_Today.py").run()
    assert not at.exception, at.exception
    sel = next(s for s in at.selectbox if s.label == "Machine")
    sel.set_value("M4").run()
    for page in ROUTED[1:]:
        at.switch_page(page).run()
        assert not at.exception, at.exception
        assert at.session_state["machine"] == "M4"
        m = [s for s in at.selectbox if s.label.startswith("Machine")]
        assert m and m[0].value == "M4", page
