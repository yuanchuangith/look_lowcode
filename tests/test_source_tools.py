from __future__ import annotations

import unittest
from unittest.mock import patch

from gxp_core.source_analysis import inspect_component_source, trace_api_contract


STATUS = {
    "index": {"version": 1, "exists": True},
    "repositories": {
        "frontend": {"selected": {"path": "F:/front", "branch": "develop", "commit": "a", "dirty_file_count": 0}, "index": {"fingerprint": "fa"}, "stale": False},
        "backend": {"selected": {"path": "F:/back", "branch": "develop", "commit": "b", "dirty_file_count": 0}, "index": {"fingerprint": "fb"}, "stale": False},
    },
}


class SourceToolTests(unittest.TestCase):
    def test_component_ambiguity_is_explicit(self) -> None:
        indexes = {
            "frontend/components.json": [
                {"component_type": "Same", "behavior_names": [], "selectors": [], "files": []},
                {"component_type": "Other", "behavior_names": [{"value": "Same"}], "selectors": [], "files": []},
            ],
            "frontend/component-contracts.json": [],
        }
        with patch("gxp_core.source_analysis.ensure_source_index", return_value=STATUS), patch(
            "gxp_core.source_analysis.load_index_file", side_effect=lambda path, default: indexes.get(path, default)
        ):
            result = inspect_component_source("Same")
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual(2, len(result["candidates"]))

    def test_api_wrapper_remains_unresolved_and_service_uses_interface_binding(self) -> None:
        indexes = {
            "frontend/requests.json": [{"route": "/api/datasets/save", "method": "POST", "function": "dataSave", "path": "service.ts", "line": 4, "dynamic": False, "wrapper": "@inbiz/utils"}],
            "backend/routes.json": [{"route": "/api/datasets/save", "method": "POST", "controller": "DataSetController", "action": "DataSave", "symbol_id": "App.DataSetController.DataSave(DataSaveDto)", "dto_types": ["DataSaveDto"], "path": "Controller.cs", "line": 8}],
            "backend/dto-contracts.json": [{"name": "DataSaveDto", "path": "Dto.cs", "line": 2, "properties": []}],
            "graph/backend-call-edges.json": [
                {"caller": "DataSetController.DataSave", "caller_id": "App.DataSetController.DataSave(DataSaveDto)", "target_ids": ["App.DataSetServices.BatchSaveData(DataSaveDto)"], "receiver_type": "App.IDataSetServices", "receiver": "services", "callee_member": "BatchSaveData", "path": "Controller.cs", "line": 10},
                {"caller": "DataSetController.DataSave", "receiver": "items", "callee_member": "Add", "path": "Controller.cs", "line": 11},
            ],
            "backend/symbols.json": [
                {"name": "IDataSetServices.BatchSaveData", "kind": "method", "path": "IService.cs", "line": 3},
                {"name": "DataSetServices.BatchSaveData", "symbol_id": "App.DataSetServices.BatchSaveData(DataSaveDto)", "type_id": "App.DataSetServices", "kind": "method", "path": "Service.cs", "line": 4},
                {"name": "IOtherServices.Add", "kind": "method", "path": "IOther.cs", "line": 3},
                {"name": "OtherServices.Add", "kind": "method", "path": "Other.cs", "line": 4},
            ],
            "backend/service-bindings.json": [
                {"interface": "IDataSetServices", "implementation": "DataSetServices", "interface_id": "App.IDataSetServices", "implementation_id": "App.DataSetServices"},
                {"interface": "IOtherServices", "implementation": "OtherServices"},
            ],
        }
        with patch("gxp_core.source_analysis.ensure_source_index", return_value=STATUS), patch(
            "gxp_core.source_analysis.load_index_file", side_effect=lambda path, default: indexes.get(path, default)
        ):
            result = trace_api_contract("/api/datasets/save", "POST")
        self.assertEqual("wrapper_unresolved", result["contract_status"])
        self.assertEqual(["DataSetServices.BatchSaveData"], [item["name"] for item in result["service_implementations"]])


if __name__ == "__main__":
    unittest.main()
