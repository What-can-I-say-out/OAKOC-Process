"""登记 OAKOC 分析函数，并提供暂时可运行的示例实现。

五项 OAKOC 内容由六个计算节点实现：关键地形先形成候选，再在接近路线计算
之后复核。这里仅检查输入、执行顺序和输出格式，不执行真实空间计算。
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .models import (
    AnalysisFinding,
    AnalysisKind,
    AvailabilityStatus,
    AnalysisResult,
    ConfidenceAssessment,
    ConfidenceLevel,
    PreparedContext,
    ResultScope,
    StageId,
)


# 每个分析函数都接收准备好的上下文和前面步骤的结果，并返回一个分析结果。
Analyzer = Callable[[PreparedContext, Mapping[AnalysisKind, AnalysisResult]], AnalysisResult]


# 加上 dataclass 后，Python 会自动生成保存下面四个字段的初始化方法。
@dataclass
class AnalyzerSpec:
    """把一个分析函数、对应步骤和必须先完成的分析放在一起。"""

    kind: AnalysisKind  # 本节点必须返回的结果类型。
    stage: StageId  # 本节点对应的流程阶段。
    depends_on: tuple[AnalysisKind, ...]  # 运行本分析前必须已经得到的结果。
    analyzer: Analyzer  # 真正执行本项分析的函数。


def _demo_result(
    context: PreparedContext,
    previous: Mapping[AnalysisKind, AnalysisResult],
    kind: AnalysisKind,
    title: str,
    pending_work: str,
) -> AnalysisResult:
    """生成明确标注的示例结果，只检查输入和前后步骤是否正确传递。"""

    request = context.request  # 结果范围来自标准请求，不在分析器内重新推断。
    assets = request.environment.assets  # 读取本次请求登记的数据文件或数据地址。
    # 把前面已经完成的分析名称连成文字，方便从输出中检查执行顺序。
    dependencies = ", ".join(item.value for item in previous) or "无"
    # 每份结果都要写明区域、适用主体、有效时间和使用的规则版本。
    scope = ResultScope(
        analysis_area=request.environment.analysis_area.id,
        perspective=request.control.analysis_perspective,
        valid_time=request.control.time_windows,
        rule_set=request.control.rule_set,
    )
    # placeholder=True 会阻止这份示例结果被正式运行模式当成真实结论发布。
    return AnalysisResult(
        kind=kind,
        scope=scope,
        status=AvailabilityStatus.DEGRADED,
        summary=f"{title}阶段已完成框架级调用。",
        findings=[
            AnalysisFinding(
                title=f"{title}接口验证",
                assessment=f"输入和依赖已接收；{pending_work}尚未接入。",
                areas=[request.environment.analysis_area.id],
                evidence_source_ids=[asset.source_id or asset.id for asset in assets],
            )
        ],
        warnings=[f"demo 占位结果，不可作为实际分析结论；当前依赖：{dependencies}。"],
        confidence=ConfidenceAssessment(
            level=ConfidenceLevel.UNKNOWN,
            reasons=["当前仅验证项目框架，尚未执行领域算法。"],
        ),
        placeholder=True,
    )


def analyze_obstacles(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """障碍分析占位入口，后续替换为平台相关障碍和机动成本计算。"""

    return _demo_result(
        context, previous, AnalysisKind.OBSTACLES, "障碍分析", "障碍提取和通行成本计算"
    )


def analyze_observation_and_fire(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """观察与射界占位入口，后续替换为可视域、盲区和条件射界计算。"""

    return _demo_result(
        context,
        previous,
        AnalysisKind.OBSERVATION_AND_FIRE,
        "观察与射界",
        "表面模型视域和能力相关射界计算",
    )


def analyze_cover_and_concealment(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """隐蔽与掩蔽占位入口，后续替换为威胁相关空间分析。"""

    return _demo_result(
        context,
        previous,
        AnalysisKind.COVER_AND_CONCEALMENT,
        "隐蔽与掩蔽",
        "条件隐蔽、掩蔽和暴露计算",
    )


def analyze_key_terrain_candidates(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """候选关键地形入口，仅形成待路线复核的候选及依据。"""

    return _demo_result(
        context,
        previous,
        AnalysisKind.KEY_TERRAIN_CANDIDATES,
        "候选关键地形",
        "任务效果相关的候选识别",
    )


def analyze_approach_routes(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """接近路线占位入口，消费三项基础结果和候选关键地形。"""

    return _demo_result(
        context,
        previous,
        AnalysisKind.APPROACH_ROUTES,
        "接近路线",
        "候选路线生成、成本分解和瓶颈识别",
    )


def analyze_key_terrain_review(
    context: PreparedContext, previous: Mapping[AnalysisKind, AnalysisResult]
) -> AnalysisResult:
    """关键地形复核入口，结合任务效果与路线依赖形成最终结果。"""

    return _demo_result(
        context,
        previous,
        AnalysisKind.KEY_TERRAIN_REVIEW,
        "关键地形复核",
        "任务相关性、路线控制和替代性复核",
    )


def demo_analyzer_specs() -> tuple[AnalyzerSpec, ...]:
    """按照实际先后关系返回六个示例分析函数。"""

    # 三项基础分析互不等待，但后面的关键地形和路线分析都需要它们。
    base = (
        AnalysisKind.OBSTACLES,
        AnalysisKind.OBSERVATION_AND_FIRE,
        AnalysisKind.COVER_AND_CONCEALMENT,
    )
    # 元组中的顺序就是流程调用这些分析函数的顺序。
    return (
        AnalyzerSpec(AnalysisKind.OBSTACLES, StageId.ANALYSIS_OBSTACLES, (), analyze_obstacles),
        AnalyzerSpec(
            AnalysisKind.OBSERVATION_AND_FIRE, StageId.ANALYSIS_OBSERVATION_AND_FIRE,
            (), analyze_observation_and_fire,
        ),
        AnalyzerSpec(
            AnalysisKind.COVER_AND_CONCEALMENT, StageId.ANALYSIS_COVER_AND_CONCEALMENT,
            (), analyze_cover_and_concealment,
        ),
        AnalyzerSpec(
            AnalysisKind.KEY_TERRAIN_CANDIDATES, StageId.ANALYSIS_KEY_TERRAIN_CANDIDATES,
            base, analyze_key_terrain_candidates,
        ),
        AnalyzerSpec(
            AnalysisKind.APPROACH_ROUTES,
            StageId.ANALYSIS_APPROACH_ROUTES,
            (*base, AnalysisKind.KEY_TERRAIN_CANDIDATES),
            analyze_approach_routes,
        ),
        AnalyzerSpec(
            AnalysisKind.KEY_TERRAIN_REVIEW,
            StageId.ANALYSIS_KEY_TERRAIN_REVIEW,
            (*base, AnalysisKind.KEY_TERRAIN_CANDIDATES, AnalysisKind.APPROACH_ROUTES),
            analyze_key_terrain_review,
        ),
    )
