from typing import get_args

from arga_sdk import KnownTwinName


def test_google_workspace_twins_are_known() -> None:
    known = set(get_args(KnownTwinName))

    assert {"google_drive", "google_docs", "google_sheets"} <= known
