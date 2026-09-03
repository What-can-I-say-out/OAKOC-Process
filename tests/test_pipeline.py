"""检查流程和变量目录是否按设计工作，不检查尚未实现的地图分析算法。"""

import unittest

from OAKOCProcess import EXAMPLE_INPUT, load_request
from oakoc import (
    AnalysisKind,
    OAKOCPipeline,
    RunStatus,
    StageId,
    build_source_catalog,
    build_variable_catalog,
    demo_analyzer_specs,
)
from oakoc.analyzers import AnalyzerSpec
from oakoc.models import StageStatus


def example_request():
    """为每项测试读取一份互不影响的完整示例请求。"""

    return load_request(EXAMPLE_INPUT)


class PipelineTest(unittest.TestCase):
    def test_demo_pipeline_records_thirteen_stages(self) -> None:
        """完整 demo 应走完十三步，并明确把示例分析结果标为有限可用。"""

        result = OAKOCPipeline(demo_analyzer_specs()).run(example_request())

        # demo 没有执行真实 GIS 算法，因此成功走通框架也必须标记为降级。
        self.assertEqual(result.status, RunStatus.DEGRADED)
        self.assertEqual([item.kind for item in result.analyses], list(AnalysisKind))
        self.assertTrue(all(item.placeholder for item in result.analyses))
        self.assertEqual([item.stage for item in result.stages], list(StageId))
        self.assertEqual(len(result.stages), 13)
        self.assertFalse(result.validation_issues)

    def test_failed_dependency_skips_aggregate_and_synthesis(self) -> None:
        """基础分析失败后，所有依赖它的后续分析都应跳过。"""

        # 这个局部函数主动抛出错误，用来模拟障碍分析执行失败。
        def fail_obstacle_analysis(context, previous):
            raise RuntimeError("障碍分析测试失败")

        # 只替换障碍分析函数，其他五项分析仍使用原来的示例实现。
        specs = list(demo_analyzer_specs())
        specs[0] = AnalyzerSpec(
            AnalysisKind.OBSTACLES,
            StageId.ANALYSIS_OBSTACLES,
            (),
            fail_obstacle_analysis,
        )
        result = OAKOCPipeline(specs).run(example_request())
        stages = {item.stage: item for item in result.stages}

        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(stages[StageId.ANALYSIS_OBSTACLES].status, StageStatus.FAILED)
        self.assertEqual(stages[StageId.ANALYSIS_FOUNDATION_AGGREGATE].status, StageStatus.SKIPPED)
        self.assertEqual(stages[StageId.ANALYSIS_KEY_TERRAIN_CANDIDATES].status, StageStatus.SKIPPED)
        self.assertEqual(stages[StageId.ANALYSIS_APPROACH_ROUTES].status, StageStatus.SKIPPED)
        self.assertEqual(stages[StageId.ANALYSIS_KEY_TERRAIN_REVIEW].status, StageStatus.SKIPPED)
        self.assertEqual(len(result.validation_issues), 4)

    def test_preparation_reports_crs_conversion(self) -> None:
        """输入数据坐标系不一致时，应明确记录后续需要坐标转换。"""

        request = example_request()
        request.environment.assets[1].crs = "EPSG:3857"
        result = OAKOCPipeline(demo_analyzer_specs()).run(request)

        self.assertEqual(result.status, RunStatus.DEGRADED)
        self.assertIn("部分输入图层需要转换到目标坐标参考系。", result.context.quality_issues)

    def test_requirement_manifest_reports_missing_conditional_input(self) -> None:
        """请求射界分析却没有火力设置时，应报告变量缺口和受影响步骤。"""

        request = example_request()
        request.control.fire_profiles.clear()
        result = OAKOCPipeline(demo_analyzer_specs()).run(request)

        manifest = result.context.requirement_manifest
        self.assertIn("parameter.fire_profile", manifest.unresolved_variable_ids)
        self.assertIn(StageId.ANALYSIS_OBSERVATION_AND_FIRE, manifest.blocked_stages)
        self.assertIn("parameter.fire_profile", result.output.data_gap_report)

    def test_unrequested_analysis_variables_are_not_required(self) -> None:
        """只请求障碍分析时，不应强制要求其他分析专用的变量。"""

        request = example_request()
        request.control.requested_analyses = [AnalysisKind.OBSTACLES]
        request.control.sensor_profiles.clear()
        request.control.fire_profiles.clear()
        request.control.route_terminals = None
        result = OAKOCPipeline(demo_analyzer_specs()).run(request)
        required = set(result.context.requirement_manifest.required_variable_ids)

        self.assertIn("result.obstacle_zones", required)
        self.assertNotIn("result.viewshed", required)
        self.assertNotIn("result.key_terrain_review", required)
        self.assertNotIn("parameter.fire_profile", result.output.data_gap_report)
        self.assertEqual([item.kind for item in result.analyses], [AnalysisKind.OBSTACLES])

    def test_production_mode_rejects_placeholder_results(self) -> None:
        """正式运行模式不能把 demo 的示例结果当成真实结果发布。"""

        result = OAKOCPipeline(demo_analyzer_specs(), mode="production").run(
            example_request()
        )

        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertIn("production 模式不接受 placeholder 分析结果。", result.validation_issues)


class CatalogTest(unittest.TestCase):
    def test_catalogs_cover_core_variables_and_sources(self) -> None:
        """目录应包含核心变量和来源，公开来源不能直接声称提供分析结论。"""

        variables = build_variable_catalog()
        sources = build_source_catalog()

        variable_ids = {item.variable_id for item in variables}
        source_ids = {item.source_id for item in sources}
        self.assertIn("context.aoi", variable_ids)
        self.assertIn("result.key_terrain_review", variable_ids)
        self.assertIn("copernicus.dem.glo30", source_ids)
        self.assertIn("osm.overpass", source_ids)
        provided = {variable_id for source in sources for variable_id in source.provides}
        self.assertIn("raster.elevation", provided)
        self.assertIn("entity.transport_network", provided)
        self.assertNotIn("result.obstacle_zones", provided)


if __name__ == "__main__":
    unittest.main()
