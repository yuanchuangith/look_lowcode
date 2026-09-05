from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from gxp_core.source_index import _combine_route, _scan_backend, _scan_frontend, refresh_source_index


class SourceIndexParserTests(unittest.TestCase):
    def test_route_composition_variants(self) -> None:
        self.assertEqual("/api/datasets/save", _combine_route("api/datasets", "save", "DataSet"))
        self.assertEqual("/api/Users/search", _combine_route("api/[controller]", "search", "Users"))
        self.assertEqual("/absolute", _combine_route("api/base", "/absolute", "Base"))
        self.assertEqual("/absolute", _combine_route("api/base", "~/absolute", "Base"))
        self.assertEqual("/api/Files/{id?}", _combine_route("api/{controller}", "{id?}", "Files"))

    def test_frontend_component_request_and_filter_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            designer = root / "src/core/components/form/training/TestPaper/designer"
            runtime = root / "src/core/components/form/training/TestPaper/preview/web"
            designer.mkdir(parents=True)
            runtime.mkdir(parents=True)
            (designer / "schema.tsx").write_text(
                "export const Behavior = createBehavior({ name: 'TestPaper', selector: n => n.props?.['x-component'] === 'TestPaper' });\n",
                encoding="utf-8",
            )
            (runtime / "service.ts").write_text(
                "export async function SearchDataCenter(postData) {\n"
                " let url = gxpUrl + '/api/datasets/search';\n"
                " return request.post(url, { data: postData });\n}\n",
                encoding="utf-8",
            )
            data, failures = _scan_frontend(root)
        self.assertEqual([], failures)
        self.assertEqual("TestPaper", data["components"][0]["component_type"])
        self.assertEqual("/api/datasets/search", data["requests"][0]["route"])
        self.assertEqual("POST", data["requests"][0]["method"])

    def test_backend_route_dto_binding_and_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "GxP2.Web/Controllers/Data"
            service = root / "GxP2.Services/Data"
            interface = root / "GxP2.IServices/Data"
            dto = root / "GxP2.Model/Dto/Data"
            for path in (controller, service, interface, dto):
                path.mkdir(parents=True)
            (controller / "DataSetController.cs").write_text(
                '[Route("api/datasets")]\npublic class DataSetController : Controller {\n'
                '[HttpPost("save")]\npublic IActionResult Save(DataSaveDto dto) { return services.BatchSaveData(dto); }\n}\n',
                encoding="utf-8",
            )
            (interface / "IDataSetServices.cs").write_text(
                "public interface IDataSetServices { bool BatchSaveData(DataSaveDto dto); }\n",
                encoding="utf-8",
            )
            (service / "DataSetServices.cs").write_text(
                "public class DataSetServices : ServicesBase, IDataSetServices {\n"
                "public bool BatchSaveData(DataSaveDto dto) { Db.Insert<object>(); return true; }\n}\n",
                encoding="utf-8",
            )
            (dto / "DataSaveDto.cs").write_text(
                "public class DataSaveDto { public string Key { get; set; } }\n",
                encoding="utf-8",
            )
            data, failures = _scan_backend(root)
        self.assertEqual([], failures)
        self.assertEqual("/api/datasets/save", data["routes"][0]["route"])
        self.assertEqual(["DataSaveDto"], data["routes"][0]["dto_types"])
        self.assertIn("IDataSetServices", {item["interface"] for item in data["service_bindings"]})
        self.assertIn("DataSetController.Save", {item["caller"] for item in data["call_edges"]})

    def test_refresh_failure_preserves_old_layer_while_other_layer_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            index = runtime / "source-index"
            (index / "frontend").mkdir(parents=True)
            (index / "frontend" / "sentinel.json").write_text('{"old": true}', encoding="utf-8")
            (index / "manifest.json").write_text('{"version": 1, "repositories": {}}', encoding="utf-8")

            def resolution(layer: str):
                return {"selected": {"path": str(runtime), "branch": "develop", "commit": layer, "dirty_file_count": 0, "remote_fingerprint": layer, "fingerprint": layer}, "mirrors": [], "checked": []}

            backend_data = {"routes": [], "symbols": [], "dto_contracts": [], "service_bindings": [], "call_edges": [], "file_count": 0}
            with patch.dict("os.environ", {"GXP_LOWCODE_RUNTIME_ROOT": str(runtime)}), patch(
                "gxp_core.source_index.resolve_repository", side_effect=resolution
            ), patch("gxp_core.source_index._scan_frontend", side_effect=RuntimeError("broken")), patch(
                "gxp_core.source_index._scan_backend", return_value=(backend_data, [])
            ):
                result = refresh_source_index(force=True)
            self.assertEqual("partial", result["status"])
            self.assertTrue((index / "frontend" / "sentinel.json").is_file())
            self.assertTrue((index / "backend" / "routes.json").is_file())


if __name__ == "__main__":
    unittest.main()
