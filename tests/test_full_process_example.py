"""使用外部 JSON 实例检查从读取请求到写出结果的完整命令行流程。"""

import tempfile
import unittest
from pathlib import Path

from OAKOCProcess import EXAMPLE_INPUT, main
from oakoc import AnalysisKind, PipelineResult, RunStatus, StageId
from oakoc.models import StageStatus


class FullProcessExampleTest(unittest.TestCase):
    def test_json_example_runs_the_complete_pipeline(self) -> None:
        """完整实例应通过命令行走完十三步，并写出六项框架分析结果。"""

        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            exit_code = main(["--input", str(EXAMPLE_INPUT), "--output", str(result_path)])
            result = PipelineResult.model_validate_json(result_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(result.status, RunStatus.DEGRADED)
        self.assertEqual([stage.stage for stage in result.stages], list(StageId))
        self.assertEqual(len(result.stages), 13)
        self.assertFalse(any(stage.status == StageStatus.FAILED for stage in result.stages))
        self.assertFalse(any(stage.status == StageStatus.SKIPPED for stage in result.stages))
        self.assertEqual(result.stages[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(result.stages[1].status, StageStatus.SUCCEEDED)
        self.assertTrue(all(stage.status == StageStatus.DEGRADED for stage in result.stages[2:]))
        self.assertEqual([analysis.kind for analysis in result.analyses], list(AnalysisKind))
        self.assertTrue(all(analysis.placeholder for analysis in result.analyses))
        self.assertFalse(result.context.requirement_manifest.unresolved_variable_ids)
        self.assertFalse(result.validation_issues)
        self.assertFalse(result.output.data_gap_report)
        self.assertEqual(result.output.structured_sections, list(AnalysisKind))
        self.assertEqual(len(result.output.map_products), len(AnalysisKind))


if __name__ == "__main__":
    unittest.main()
