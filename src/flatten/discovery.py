"""Static call-site discovery for method dispatch candidates."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from flatten._utils import normalize_filename
from flatten.contracts import CallSite


def _code_for(module: cst.Module, node: cst.CSTNode) -> str:
    return module.code_for_node(node)


class _CallSiteVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, filename: str, module: cst.Module) -> None:
        self.filename = filename
        self.module = module
        self.call_sites: list[CallSite] = []

    def visit_Call(self, node: cst.Call) -> None:
        if not isinstance(node.func, cst.Attribute):
            return
        receiver = node.func.value
        method = node.func.attr.value
        position = self.get_metadata(PositionProvider, node)
        call_site_id = (
            f"{self.filename}:{position.start.line}:{position.start.column}-"
            f"{position.end.line}:{position.end.column}"
        )
        receiver_expr = _code_for(self.module, receiver)
        self.call_sites.append(
            CallSite(
                call_site_id=call_site_id,
                filename=self.filename,
                line=position.start.line,
                column=position.start.column,
                end_line=position.end.line,
                end_column=position.end.column,
                qualified_name=f"{receiver_expr}.{method}",
                receiver_expr=receiver_expr,
                method_name=method,
            )
        )


def discover_call_sites(source: str, *, filename: str = "<memory>") -> list[CallSite]:
    """Return position-identified ``obj.method(...)`` call candidates."""
    # `normalize_filename` rather than a resolve() here. The old guard special-cased
    # exactly one virtual name, the default "<memory>", so every *other* angle-bracket
    # filename a caller supplies -- "<fuzz>" from the property tests, "<p1>" from the
    # SI regressions, CPython's own "<string>" -- reached Path.resolve(). On Windows
    # under Python <= 3.9 that raises OSError [WinError 123]: `<` and `>` are illegal
    # in a path, and resolve() called _getfinalpathname on it. 3.10 rewrote resolve()
    # to stop raising, which is why this only ever went red on two matrix cells.
    # `normalize_filename` already guards the whole `<...>` class and is the same
    # function tracer.py and _cli_orchestration.py use, so this also removes the
    # third private copy of the rule.
    filename = normalize_filename(filename)
    module = cst.parse_module(source)
    wrapper = MetadataWrapper(module)
    visitor = _CallSiteVisitor(filename, module)
    wrapper.visit(visitor)
    return visitor.call_sites
