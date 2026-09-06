from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "mcp"))

import server
from gxp_core.canvas import CanvasInspector
from gxp_core.diagnostics import DiagnosticEngine
from gxp_core.service import GxpReadonlyService


class FixtureRepository:
    def resolve_action(self, identifier):
        return [{"ref_id": "FIXTURE1", "action_code": "FIXTURE1"}]

    def resolve_actions(self, tokens):
        return []

    def search_actions(self, query, **kwargs):
        return []

    def search_pages(self, query, **kwargs):
        return []

    def search_design_text(self, text, **kwargs):
        return []

    def load_design(self, ref_id, **kwargs):
        return {"design_id": "fixture-v1", "version": "published", "is_deleted": 0, "metadata": self.resolve_action(ref_id)[0], "csharp_code": 'class Generated { void main() { var chosen = row["file_ver_id"]; } }', "data_json": {"actionData": [{"key": "main", "title": "main", "data": [{"key": "value", "title": "Define", "elementKey": "SetVariable", "paramsValue": {"inputParams": {"variableValue": {"code": 'row["file_ver_id"]'}, "variableType": "string"}, "outputParams": {"variableName": {"code": "chosen"}}}}]}]}}


service = object.__new__(GxpReadonlyService)
service.repository = FixtureRepository()
service.inspector = CanvasInspector()
service.diagnostics = DiagnosticEngine(service.repository, service.inspector)
server.service = lambda: service
local = len(sys.argv) < 3 or sys.argv[2] != "http-registry"
app = server.create_mcp(include_local_cpm=local, include_local_schema=local, include_local_source=local)
app.run(transport="stdio")
