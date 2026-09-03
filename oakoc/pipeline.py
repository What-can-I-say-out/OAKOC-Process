"""按照 OAKOC 的十三个步骤安排数据准备、分析和发布。

结果中仍会分别记录十三个步骤，便于看到每一步是否完成；代码内部按需求、
数据准备、基础分析、综合分析和发布五个部分组织，避免拆成过多小文件。
当前只搭好运行框架，不下载公开数据、不做地图计算，也不生成实际地图。
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from .analyzers import AnalyzerSpec
from .catalog import CATALOG_VERSION, build_variable_catalog
from .models import (
    AcquisitionMode,
    AnalysisKind,
    AnalysisRequest,
    AvailabilityStatus,
    AnalysisResult,
    PipelineResult,
    PreparedContext,
    PublishedOutput,
    RequirementManifest,
    RequirementLevel,
    RunStatus,
    StageId,
    StageRecord,
    StageStatus,
    VariableBinding,
    VariableSpec,
)


def _now() -> datetime:
    """返回当前 UTC 时间，避免不同机器的本地时区造成时间误解。"""

    return datetime.now(timezone.utc)


def _record(
    stage: StageId, status: StageStatus, started_at: datetime, message: str = ""
) -> StageRecord:
    """生成一条步骤记录，并自动填写当前完成时间。"""

    # 调用方传入开始时间，本函数在步骤结束时补上完成时间。
    return StageRecord(
        stage=stage, status=status, started_at=started_at, completed_at=_now(), message=message
    )


def _requested_kinds(request: AnalysisRequest) -> set[AnalysisKind]:
    """把用户请求的分析和这些分析必须依赖的前面分析合并起来。"""

    # set 会自动去掉重复项，也方便后面判断某项分析是否已被请求。
    requested = set(request.control.requested_analyses)
    # 障碍、观察与射界、隐蔽与掩蔽是三项基础分析。
    base = {
        AnalysisKind.OBSTACLES,
        AnalysisKind.OBSERVATION_AND_FIRE,
        AnalysisKind.COVER_AND_CONCEALMENT,
    }
    # 最终确认关键地形前，必须先得到候选关键地形和接近路线。
    if AnalysisKind.KEY_TERRAIN_REVIEW in requested:
        requested.update({AnalysisKind.KEY_TERRAIN_CANDIDATES, AnalysisKind.APPROACH_ROUTES})
    # 接近路线要使用候选关键地形，因此只请求路线时也要补上候选分析。
    if AnalysisKind.APPROACH_ROUTES in requested:
        requested.add(AnalysisKind.KEY_TERRAIN_CANDIDATES)
    # 任何综合分析都以三项基础分析为输入，所以最后统一补齐它们。
    if requested & {
        AnalysisKind.KEY_TERRAIN_CANDIDATES,
        AnalysisKind.APPROACH_ROUTES,
        AnalysisKind.KEY_TERRAIN_REVIEW,
    }:
        requested.update(base)
    return requested


def _stage_is_active(stage: StageId, requested: set[AnalysisKind]) -> bool:
    """判断某个变量所在的步骤是否会在本次任务中执行。"""

    # 把分析步骤对应到分析类型，数据准备和发布步骤不在这张表中。
    analysis_kind = {
        StageId.ANALYSIS_OBSTACLES: AnalysisKind.OBSTACLES,
        StageId.ANALYSIS_OBSERVATION_AND_FIRE: AnalysisKind.OBSERVATION_AND_FIRE,
        StageId.ANALYSIS_COVER_AND_CONCEALMENT: AnalysisKind.COVER_AND_CONCEALMENT,
        StageId.ANALYSIS_KEY_TERRAIN_CANDIDATES: AnalysisKind.KEY_TERRAIN_CANDIDATES,
        StageId.ANALYSIS_APPROACH_ROUTES: AnalysisKind.APPROACH_ROUTES,
        StageId.ANALYSIS_KEY_TERRAIN_REVIEW: AnalysisKind.KEY_TERRAIN_REVIEW,
    }.get(stage)
    # 普通分析步骤只有在本次请求包含对应分析时才参与运行。
    if analysis_kind is not None:
        return analysis_kind in requested
    # 基础结果汇总只在后面存在关键地形或路线分析时才需要。
    if stage == StageId.ANALYSIS_FOUNDATION_AGGREGATE:
        return bool(
            requested
            & {
                AnalysisKind.KEY_TERRAIN_CANDIDATES,
                AnalysisKind.APPROACH_ROUTES,
                AnalysisKind.KEY_TERRAIN_REVIEW,
            }
        )
    # 需求、数据准备和发布等公共步骤每次都要执行。
    return True


def _is_required(variable: VariableSpec, requested: set[AnalysisKind]) -> bool:
    """结合本次请求，判断目录中的一个变量这次是否必须存在。"""

    # 不执行变量所属的分析步骤时，这个变量本次自然不属于必需项。
    if not _stage_is_active(variable.stage, requested):
        return False
    # 标为 REQUIRED 的变量只要所在步骤执行，就直接列入需求。
    if variable.requirement_level == RequirementLevel.REQUIRED:
        return True
    # 条件必要变量按照具体分析内容判断，未列出的可选变量不会被强制要求。
    required_conditions = {
        "context.effect_criteria": bool(
            requested & {AnalysisKind.KEY_TERRAIN_CANDIDATES, AnalysisKind.KEY_TERRAIN_REVIEW}
        ),
        "parameter.mobility_profile": bool(
            requested & {AnalysisKind.OBSTACLES, AnalysisKind.APPROACH_ROUTES}
        ),
        "parameter.sensor_profile": bool(
            requested
            & {AnalysisKind.OBSERVATION_AND_FIRE, AnalysisKind.COVER_AND_CONCEALMENT}
        ),
        "parameter.fire_profile": bool(
            requested & {AnalysisKind.OBSERVATION_AND_FIRE, AnalysisKind.COVER_AND_CONCEALMENT}
        ),
        "context.route_terminals": bool(
            requested & {AnalysisKind.APPROACH_ROUTES, AnalysisKind.KEY_TERRAIN_REVIEW}
        ),
        "derived.surface_height_model": AnalysisKind.OBSERVATION_AND_FIRE in requested,
        "result.fire_coverage": AnalysisKind.OBSERVATION_AND_FIRE in requested,
        "result.fire_dead_zones": AnalysisKind.OBSERVATION_AND_FIRE in requested,
        "result.route_windows": False,
    }
    # 找不到对应条件时返回 False，表示当前没有理由把它列为必要变量。
    return required_conditions.get(variable.variable_id, False)


def _task_values(request: AnalysisRequest) -> dict[str, object]:
    """把请求中已经填写的内容对应到变量目录中的英文编号。"""

    # control 会在下面重复使用，先取出可以让每一行映射更短、更容易读。
    control = request.control
    # 左边是变量目录编号，右边是本次请求中的实际内容。
    return {
        "context.aoi": request.environment.analysis_area.model_dump(mode="json"),
        "context.time_window": [item.model_dump(mode="json") for item in control.time_windows],
        "context.analysis_perspective": control.analysis_perspective,
        "context.mission_phase": request.mission.phase,
        "context.mission_objective": {
            "objective": request.mission.objective,
            "desired_end_state": request.mission.desired_end_state,
        },
        "context.effect_criteria": [request.mission.desired_end_state],
        "context.requested_analyses": [item.value for item in control.requested_analyses],
        "context.rule_set_ref": control.rule_set.model_dump(mode="json"),
        "parameter.mobility_profile": [item.model_dump(mode="json") for item in control.platform_profiles],
        "parameter.sensor_profile": [item.model_dump(mode="json") for item in control.sensor_profiles],
        "parameter.fire_profile": [item.model_dump(mode="json") for item in control.fire_profiles],
        "context.route_terminals": control.route_terminals,
        "context.task_constraints": control.task_constraints,
        "parameter.target_crs": control.target_crs,
        "parameter.analysis_resolution": control.analysis_resolution_m,
    }


def _provided_variables(request: AnalysisRequest) -> set[str]:
    """汇总任务方已填写的变量，以及数据文件声明可以提供的变量。"""

    # 空列表、空文字和 None 都不算已经提供的有效内容。
    provided = {variable_id for variable_id, value in _task_values(request).items() if value}
    # 一个数据文件可以声明提供多个变量，这里把它们合并到同一个集合中。
    for asset in request.environment.assets:
        provided.update(asset.variable_ids)
    return provided


def build_requirement_manifest(
    request: AnalysisRequest, run_id: str, variables: Sequence[VariableSpec]
) -> RequirementManifest:
    """根据本次要做的分析列出必要变量，并找出尚未提供的输入。"""

    # required_ids 保存全部必要变量，unresolved 只保存当前还没有的输入变量。
    required_ids: list[str] = []
    unresolved: list[str] = []
    # set 自动去重，避免多个缺失变量重复加入同一个受影响步骤。
    blocked_stages: set[StageId] = set()
    # 只有前两步的变量是外部输入；后面步骤的必要变量会由程序计算出来。
    input_stages = {StageId.CONTEXT_REQUIREMENTS, StageId.DATA_ACQUIRE}
    requested = _requested_kinds(request)
    provided = _provided_variables(request)
    # 逐个检查目录变量，形成只属于本次任务的需求清单。
    for variable in variables:
        required = _is_required(variable, requested)
        if required:
            required_ids.append(variable.variable_id)
        # 必要的外部输入尚未提供时，同时记录变量和它会影响的后续步骤。
        if required and variable.stage in input_stages and variable.variable_id not in provided:
            unresolved.append(variable.variable_id)
            blocked_stages.update(variable.used_by)
    # 步骤按十三步的固定顺序输出，避免 set 导致每次结果顺序不同。
    return RequirementManifest(
        run_id=run_id,
        catalog_version=CATALOG_VERSION,
        required_variable_ids=required_ids,
        unresolved_variable_ids=unresolved,
        blocked_stages=sorted(blocked_stages, key=lambda item: list(StageId).index(item)),
        generated_at=_now(),
    )


def _initial_bindings(
    request: AnalysisRequest, variables: Sequence[VariableSpec]
) -> list[VariableBinding]:
    """记录每个已提供变量的值，或者记录它来自哪个数据文件。"""

    bindings: list[VariableBinding] = []
    # 小型任务设置可以直接写进结果，不需要另外建立数据文件。
    for variable_id, value in _task_values(request).items():
        if value:
            bindings.append(
                VariableBinding(
                    variable_id=variable_id,
                    status=AvailabilityStatus.COMPLETE,
                    acquisition_mode=AcquisitionMode.TASK_CONFIG,
                    value=value,
                )
            )
    # 地图等大型数据只记录 DataAsset 编号，真正读取文件留给后续实现。
    for variable in variables:
        assets = [asset.id for asset in request.environment.assets
                  if variable.variable_id in asset.variable_ids]
        # 当前框架没有检查文件内容，因此这里只能标记为“有限可用”。
        if assets:
            bindings.append(
                VariableBinding(
                    variable_id=variable.variable_id,
                    status=AvailabilityStatus.DEGRADED,
                    acquisition_mode=AcquisitionMode.PUBLIC_DIRECT,
                    asset_ids=assets,
                    limitations=["框架仅记录资产绑定，尚未执行覆盖率、时效和内容质量检查。"],
                )
            )
    return bindings


def prepare_context(
    request: AnalysisRequest,
    manifest: RequirementManifest,
    variables: Sequence[VariableSpec],
) -> PreparedContext:
    """把请求和变量记录整理成统一输入；真正的地图转换和裁剪以后实现。"""

    # 收集分析区域和所有数据文件声明的坐标系，并自动去掉重复值。
    source_crs = (
        {request.environment.analysis_area.crs}
        | {asset.crs for asset in request.environment.assets if asset.crs}
    )
    # 用户明确指定目标坐标系时优先采用该设置。
    target_crs = request.control.target_crs
    # 未指定时，只有全部输入坐标系一致才能直接确定统一坐标系。
    canonical_crs = target_crs or (next(iter(source_crs)) if len(source_crs) == 1 else None)
    issues: list[str] = []
    # 没有任何数据文件时仍允许 demo 继续，但必须明确记录这个缺口。
    if not request.environment.assets:
        issues.append("尚未绑定数据资产；公开数据获取适配器未实现。")
    # 多种坐标系且没有目标设置时，程序暂时不知道应该统一到哪一种。
    elif len(source_crs) > 1 and target_crs is None:
        issues.append("输入图层包含多个坐标参考系，但未指定目标坐标参考系。")
    # 已指定目标坐标系但输入不一致时，后续需要实际执行坐标转换。
    elif target_crs and any(item != target_crs for item in source_crs):
        issues.append("部分输入图层需要转换到目标坐标参考系。")
    # demo 继续运行是为了验证框架；正式模式会在发布检查中拒绝必要输入缺失。
    if manifest.unresolved_variable_ids:
        issues.append("部分必要输入尚未绑定，demo 将继续验证流程并保留数据缺口。")
    # 后面的所有分析函数都读取同一份 PreparedContext。
    return PreparedContext(
        request=request,
        requirement_manifest=manifest,
        canonical_crs=canonical_crs,
        variable_bindings=_initial_bindings(request, variables),
        quality_issues=issues,
    )


class OAKOCPipeline:
    """按十三个步骤调用六项分析，并把各步状态和结果汇总起来。"""

    def __init__(
        self,
        analyzer_specs: Sequence[AnalyzerSpec],
        mode: Literal["demo", "production"] = "demo",
    ) -> None:
        # tuple 固定本次流程使用的分析函数顺序，运行过程中不会临时改变。
        self._specs = tuple(analyzer_specs)
        # demo 允许示例结果，production 只接受未来接入的真实分析结果。
        self._mode = mode
        # 流程创建时读取一次变量目录，后面所有步骤使用同一版本。
        self._variables = build_variable_catalog()

    def run(self, request: AnalysisRequest) -> PipelineResult:
        """从变量需求开始依次执行十三步；demo 允许缺少真实数据和算法。"""

        # run_id 把本次需求、步骤记录和最终结果关联起来。
        run_id = str(uuid4())
        # 每完成一个步骤就向 stages 追加一条记录。
        stages: list[StageRecord] = []

        # 第 1 步根据本次任务生成需求，不会把目录中的所有变量都当成必需项。
        started = _now()
        manifest = build_requirement_manifest(request, run_id, self._variables)
        # 尚有必要输入未提供时，本步骤已经完成，但结果要标记为有限可用。
        requirement_status = StageStatus.DEGRADED if manifest.unresolved_variable_ids else StageStatus.SUCCEEDED
        requirement_message = (
            "变量需求已生成，存在待获取项。"
            if manifest.unresolved_variable_ids else "变量需求已生成。"
        )
        stages.append(
            _record(
                StageId.CONTEXT_REQUIREMENTS,
                requirement_status,
                started,
                requirement_message,
            )
        )

        # 第 2 至 5 步分别留一条记录，但当前版本共用一段简化的数据准备代码。
        started = _now()
        # 当前没有真实下载功能，所以缺少输入时只记录问题并让 demo 继续。
        acquire_status = StageStatus.DEGRADED if manifest.unresolved_variable_ids else StageStatus.SUCCEEDED
        stages.append(
            _record(
                StageId.DATA_ACQUIRE,
                acquire_status,
                started,
                "已登记输入资产；公开数据下载适配器尚未实现。",
            )
        )
        started = _now()
        # 把请求、需求清单、坐标系和已提供变量整理成后续分析共用的输入。
        context = prepare_context(request, manifest, self._variables)
        # 只要数据准备发现问题，标准化步骤就不能标为完全成功。
        normalize_status = StageStatus.DEGRADED if context.quality_issues else StageStatus.SUCCEEDED
        stages.append(
            _record(
                StageId.DATA_NORMALIZE,
                normalize_status,
                started,
                "已建立统一上下文；尚未执行实际重投影、裁剪和时空对齐。",
            )
        )
        started = _now()
        stages.append(
            _record(
                StageId.DATA_QUALITY_AND_DERIVE,
                StageStatus.DEGRADED,
                started,
                "质量记录格式和计算变量目录已建立；尚未执行实际地图计算。",
            )
        )
        started = _now()
        stages.append(
            _record(
                StageId.BASELINE_BUILD,
                StageStatus.DEGRADED,
                started,
                "已形成框架基线；数据是否达到分析要求仍待后续代码检查。",
            )
        )

        # 第 6 至 12 步按照前后依赖顺序执行，三项基础结果汇总仍单独记为一步。
        # 字典按分析类型保存成功返回的结果，后面的分析可以直接按类型取用。
        results: dict[AnalysisKind, AnalysisResult] = {}
        requested = _requested_kinds(request)
        # _specs 已按正确先后顺序排列，因此这里用一个循环依次执行即可。
        for spec in self._specs:
            # 执行第一个综合分析前，先插入第 9 步“三项基础结果汇总”。
            if spec.kind == AnalysisKind.KEY_TERRAIN_CANDIDATES:
                self._append_foundation_aggregate(stages, results)
            stage_id = spec.stage
            started = _now()
            # 用户没有请求的分析保留步骤记录，但不调用对应函数。
            if spec.kind not in requested:
                stages.append(_record(stage_id, StageStatus.SKIPPED, started, "本次任务未请求该分析。"))
                continue
            # 只有真正生成并保存到 results 的前置结果才算成功依赖。
            missing = [item for item in spec.depends_on if item not in results]
            if missing:
                names = ", ".join(item.value for item in missing)
                stages.append(
                    _record(stage_id, StageStatus.SKIPPED, started, f"缺少成功的依赖结果：{names}。")
                )
                continue
            try:
                # 只把当前分析声明需要的前置结果传进去，避免依赖不相关内容。
                dependencies = {item: results[item] for item in spec.depends_on}
                result = spec.analyzer(context, dependencies)
                # 分析函数正常返回后才保存结果；发生异常时不会留下半成品。
                results[spec.kind] = result
                # 分析结果不是 COMPLETE 时，对应步骤也只能标记为有限可用。
                status = (
                    StageStatus.DEGRADED
                    if result.status != AvailabilityStatus.COMPLETE
                    else StageStatus.SUCCEEDED
                )
                stages.append(_record(stage_id, status, started, "分析节点执行完成。"))
            except Exception as exc:
                # 一项分析失败后记录错误；依赖它的后续分析会因 missing 自动跳过。
                stages.append(_record(stage_id, StageStatus.FAILED, started, str(exc)))

        # 第 13 步检查所需结果是否齐全，并生成最终成果清单。
        started = _now()
        # requested 与已有结果做差集，即可找出应该生成但没有生成的结果。
        missing_results = sorted(requested - results.keys(), key=lambda item: item.value)
        validation_issues = [f"缺少分析结果：{item.value}" for item in missing_results]
        # 正式运行不允许带着必要输入缺口发布，demo 则保留缺口继续展示流程。
        if self._mode == "production" and manifest.unresolved_variable_ids:
            names = ", ".join(manifest.unresolved_variable_ids)
            validation_issues.append(f"production 模式存在未绑定的必要输入：{names}")
        # placeholder 是本项目当前的示例结果，不能冒充真实分析结果正式发布。
        if self._mode == "production" and any(result.placeholder for result in results.values()):
            validation_issues.append("production 模式不接受 placeholder 分析结果。")
        # 先得出整次运行状态，再使用相同文字值填写第 13 步的状态。
        status = self._run_status(validation_issues, context, list(results.values()))
        publish_status = StageStatus(status.value)
        stages.append(
            _record(
                StageId.PUBLISH_VALIDATE_AND_RELEASE,
                publish_status,
                started,
                "综合校验完成。" if not validation_issues else "综合结果不完整。",
            )
        )
        # 按分析函数登记顺序输出结果，保证每次 JSON 中的顺序一致。
        ordered_results = [results[spec.kind] for spec in self._specs if spec.kind in results]
        output = self._publish(ordered_results, status, context)
        # PipelineResult 把运行中产生的全部内容包装成一个统一返回值。
        return PipelineResult(
            run_id=run_id,
            mode=self._mode,
            status=status,
            context=context,
            stages=stages,
            analyses=ordered_results,
            validation_issues=validation_issues,
            output=output,
        )

    @staticmethod
    def _append_foundation_aggregate(
        stages: list[StageRecord], results: dict[AnalysisKind, AnalysisResult]
    ) -> None:
        """记录三项基础分析是否都已完成，不编造尚未计算的汇总数值。"""

        started = _now()
        # 这三项结果是候选关键地形、接近路线和最终复核的共同基础。
        base = {
            AnalysisKind.OBSTACLES,
            AnalysisKind.OBSERVATION_AND_FIRE,
            AnalysisKind.COVER_AND_CONCEALMENT,
        }
        # 集合相减可以直接得到还没有成功生成的基础结果。
        missing = base - results.keys()
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            # 基础结果不全时跳过汇总，并让后续分析按各自依赖继续判断。
            stages.append(
                _record(
                    StageId.ANALYSIS_FOUNDATION_AGGREGATE,
                    StageStatus.SKIPPED,
                    started,
                    f"缺少基础分析结果：{names}。",
                )
            )
            return
        # 当前框架只确认三个结果齐全，尚未比较它们的空间位置或相互冲突。
        stages.append(
            _record(
                StageId.ANALYSIS_FOUNDATION_AGGREGATE,
                StageStatus.DEGRADED,
                started,
                "基础结果引用已汇聚；冲突检测和空间对齐尚未实现。",
            )
        )

    def _run_status(
        self,
        validation_issues: list[str],
        context: PreparedContext,
        results: list[AnalysisResult],
    ) -> RunStatus:
        """根据结果是否完整、数据是否有问题，确定整次运行的最终状态。"""

        # 缺少所需分析结果或违反正式运行规则时，整次任务直接失败。
        if validation_issues:
            return RunStatus.FAILED
        # 没有阻断问题但数据或某项结果受限时，任务状态为 DEGRADED。
        degraded = context.quality_issues or any(
            item.status in {AvailabilityStatus.PARTIAL, AvailabilityStatus.DEGRADED}
            for item in results
        )
        return RunStatus.DEGRADED if degraded else RunStatus.SUCCEEDED

    def _publish(
        self,
        results: list[AnalysisResult],
        status: RunStatus,
        context: PreparedContext,
    ) -> PublishedOutput:
        """生成最终成果清单；实际地图文件留给后续发布代码生成。"""

        # 先提取已经完成的分析类型，用它们生成结构化章节和地图待办项。
        kinds = [result.kind for result in results]
        # demo 的结论必须明确说明它只验证框架，不能作为实际地形判断。
        if status != RunStatus.FAILED and self._mode == "demo":
            conclusion = "OAKOC demo 管线执行完成；结果仅验证框架，不代表实际分析结论。"
        elif status == RunStatus.SUCCEEDED:
            conclusion = "OAKOC 分析管线执行完成。"
        else:
            conclusion = "OAKOC 分析管线未形成可发布的完整结果，请检查数据缺口和失败阶段。"
        # 每项完成的分析未来都应对应一份专题地图。
        map_products = [f"{kind.value} 专题地图（待渲染器实现）" for kind in kinds]
        # 只有 demo 固定提示地图尚未生成；正式模式的警告应来自真实发布代码。
        warnings = ["尚未生成实际地图文件。"] if self._mode == "demo" else []
        return PublishedOutput(
            map_products=map_products,
            structured_sections=kinds,
            data_gap_report=context.requirement_manifest.unresolved_variable_ids,
            conclusion=conclusion,
            warnings=warnings,
        )
