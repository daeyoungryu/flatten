"""Static call-site discovery for method dispatch candidates."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

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
    module = cst.parse_module(source)
    wrapper = MetadataWrapper(module)
    visitor = _CallSiteVisitor(filename, module)
    wrapper.visit(visitor)
    return visitor.call_sites
