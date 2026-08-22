"""A virtual filename must survive discovery untouched.

`discover_call_sites` used to resolve any filename that was not literally
"<memory>", which meant every other angle-bracket name a caller passes --
"<fuzz>" from the property tests, "<p1>" from the SI regressions, CPython's own
"<string>" -- was handed to `Path.resolve()`. Two things came of that:

* on Windows under Python <= 3.9 it raised `OSError [WinError 123]`, because
  `<` and `>` are illegal in a path and `resolve()` called `_getfinalpathname`
  on it. 3.10 rewrote `resolve()` to stop raising, so the bug was invisible on
  8 of the 10 matrix cells and red on 2.
* everywhere else it silently produced `<cwd>/<fuzz>`, a path that does not
  exist and never did, and stamped it into every `call_site_id`.

So asserting "does not raise" would only pin the Windows half. These assert the
exact passthrough, which pins both, and the resolution of a real path next to
it, so a fix that simply stopped normalising anything would not pass.
"""

from __future__ import annotations

from pathlib import Path

from flatten.discovery import discover_call_sites

SOURCE = "def f(o):\n    return o.method(1)\n"


def test_angle_bracket_filenames_pass_through_unchanged() -> None:
    for virtual in ("<memory>", "<fuzz>", "<p1>", "<string>", "<stdin>"):
        sites = discover_call_sites(SOURCE, filename=virtual)
        assert sites, f"expected the call site to be discovered for {virtual}"
        assert sites[0].filename == virtual
        assert sites[0].call_site_id.startswith(virtual + ":")


def test_a_real_path_is_still_resolved(tmp_path: Path) -> None:
    """The neighbouring legitimate case: real filenames still become absolute."""
    target = tmp_path / "sample.py"
    target.write_text(SOURCE, encoding="utf-8")
    sites = discover_call_sites(SOURCE, filename=str(target))
    assert sites
    resolved = str(target.resolve()).replace("\\", "/")
    assert sites[0].filename == resolved
    assert Path(sites[0].filename).is_absolute()


def test_an_empty_filename_is_left_alone() -> None:
    sites = discover_call_sites(SOURCE, filename="")
    assert sites
    assert sites[0].filename == ""
