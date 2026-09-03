"""统一规定 OAKOC 流程中各类数据应该包含哪些字段。

本文件把“目录里定义了什么变量”“本次需要什么变量”“本次实际拿到了什么数据”
和“数据质量如何”分开记录。这样可以避免把目录中存在某项数据，误写成本次任务
已经取得并检查过该数据。本文件只定义数据格式，不做地图计算、数值判断或下载。
"""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, JsonValue, model_validator


# 路线至少要有起点和终点，因此字符串列表的长度不能少于 2。
RouteControlPoints = Annotated[list[str], Field(min_length=2)]


# 同时继承 str 和 Enum 后，固定选项既能限制取值，也能直接写入 JSON 字符串。
class AnalysisKind(str, Enum):
    """六项分析结果名称；关键地形分成首次筛选和路线分析后的再次确认。"""

    OBSTACLES = "obstacles"  # 障碍分析。
    OBSERVATION_AND_FIRE = "observation_and_fire"  # 观察与射界分析。
    COVER_AND_CONCEALMENT = "cover_and_concealment"  # 隐蔽与掩蔽分析。
    KEY_TERRAIN_CANDIDATES = "key_terrain_candidates"  # 初步筛出的关键地形候选。
    APPROACH_ROUTES = "approach_routes"  # 接近路线分析。
    KEY_TERRAIN_REVIEW = "key_terrain_review"  # 结合路线结果再次确认关键地形。


class StageId(str, Enum):
    """十三个流程步骤；每一步都单独记状态，代码内部仍按五大部分组织。"""

    CONTEXT_REQUIREMENTS = "context.requirements"  # 1. 根据任务整理变量需求。
    DATA_ACQUIRE = "data.acquire"  # 2. 获取公开、任务和观测数据。
    DATA_NORMALIZE = "data.normalize"  # 3. 统一名称、位置、时间和单位。
    DATA_QUALITY_AND_DERIVE = "data.quality_and_derive"  # 4. 检查质量并计算公共地形数据。
    BASELINE_BUILD = "baseline.build"  # 5. 建立后续分析共用的基础数据。
    ANALYSIS_OBSTACLES = "analysis.obstacles"  # 6. 分析障碍。
    # 下面几个英文值较长，把中文解释放到上一行会更容易阅读。
    ANALYSIS_OBSERVATION_AND_FIRE = "analysis.observation_and_fire"  # 7. 观察与射界。
    ANALYSIS_COVER_AND_CONCEALMENT = "analysis.cover_and_concealment"  # 8. 隐蔽与掩蔽。
    ANALYSIS_FOUNDATION_AGGREGATE = "analysis.foundation_aggregate"  # 9. 汇总基础结果。
    ANALYSIS_KEY_TERRAIN_CANDIDATES = "analysis.key_terrain_candidates"  # 10. 筛选候选。
    ANALYSIS_APPROACH_ROUTES = "analysis.approach_routes"  # 11. 分析接近路线。
    ANALYSIS_KEY_TERRAIN_REVIEW = "analysis.key_terrain_review"  # 12. 再次确认关键地形。
    PUBLISH_VALIDATE_AND_RELEASE = "publish.validate_and_release"  # 13. 检查并发布结果。


class StageStatus(str, Enum):
    """单个步骤的执行状态。"""

    SUCCEEDED = "succeeded"  # 已正常完成。
    DEGRADED = "degraded"  # 已完成，但数据不足或功能仍是简化版本。
    FAILED = "failed"  # 执行过程中出现错误。
    SKIPPED = "skipped"  # 未被请求，或者前面所需结果没有成功生成。


class RunStatus(str, Enum):
    """完整任务的最终状态。"""

    SUCCEEDED = "succeeded"  # 所需结果完整且没有已知限制。
    DEGRADED = "degraded"  # 流程完成，但结果带有明确限制。
    FAILED = "failed"  # 没有形成完整的所需结果。


class DataRole(str, Enum):
    """变量在流程中扮演的角色；质量另行记录，不与业务变量混在一起。"""

    CONTEXT = "context"  # 任务区域、时间和分析对象等运行背景。
    ENTITY = "entity"  # 道路、建筑、水系等地图对象。
    RASTER = "raster"  # 高程、土地覆盖、天气等网格数据。
    OBSERVATION = "observation"  # 现场、情报或人工记录的动态情况。
    PARAMETER = "parameter"  # 平台、传感器、射程和分辨率等运行设置。
    DERIVED = "derived"  # 程序根据其他数据计算得到的变量。
    RESULT = "result"  # 某一步分析得到的结果。


class ValueType(str, Enum):
    """变量内容的基本类型，与 GeoTIFF、GeoJSON 等保存格式不是一回事。"""

    STRING = "string"  # 一段文字。
    FLOAT = "float"  # 可以带小数的数值。
    ENUM = "enum"  # 只能从固定选项中选择一个值。
    TIME_RANGE = "time_range"  # 开始和结束时间组成的范围。
    POINT = "point"  # 地图上的点。
    LINE = "line"  # 地图上的线。
    POLYGON = "polygon"  # 地图上的面。
    RASTER = "raster"  # 由规则网格组成的地图数据。
    OBJECT = "object"  # 由多个有名称字段组成的内容。
    ARRAY = "array"  # 按顺序保存的一组内容。
    REFERENCE = "reference"  # 指向另一份数据或配置的编号。


class RequirementLevel(str, Enum):
    """变量对业务是否必要；有条件必要时由 required_when 写明条件。"""

    REQUIRED = "required"  # 只要执行对应步骤就需要。
    CONDITIONAL = "conditional"  # 仅在指定条件成立时需要。
    OPTIONAL = "optional"  # 没有它也能运行，但有它可以改善结果。


class ImplementationPriority(str, Enum):
    """开发顺序；它与业务必要性分开，难以取得不等于不重要。"""

    P0 = "p0"  # 第一版必须处理。
    P1 = "p1"  # 第一版可支持，或在核心流程之后补充。


class Accessibility(str, Enum):
    """通常可以怎样取得变量，不代表本次区域一定有这些数据。"""

    DIRECT = "direct"  # 数据源可直接提供。
    DERIVABLE = "derivable"  # 可以根据其他数据计算得到。
    PROXY_ONLY = "proxy_only"  # 只能用相关数据作近似参考。
    UNAVAILABLE = "unavailable"  # 当前没有可靠的通用来源。


class AcquisitionMode(str, Enum):
    """本次任务允许从哪里取得变量。"""

    PUBLIC_DIRECT = "public_direct"  # 直接使用公开数据。
    PUBLIC_DERIVED = "public_derived"  # 根据公开数据计算。
    TASK_CONFIG = "task_config"  # 由任务方在运行前填写。
    LOCAL_OBSERVATION = "local_observation"  # 来自现场、情报或人工录入。
    HYBRID = "hybrid"  # 合并多种来源。


class AvailabilityStatus(str, Enum):
    """某项数据或分析结果在本次运行中到底能用到什么程度。"""

    COMPLETE = "complete"  # 内容完整并达到要求。
    PARTIAL = "partial"  # 只覆盖部分区域、时间或字段。
    DEGRADED = "degraded"  # 可以继续使用，但质量或方法低于目标要求。
    UNAVAILABLE = "unavailable"  # 本次没有可用内容。
    FAILED = "failed"  # 尝试获取或计算时失败。


class CoverageStatus(str, Enum):
    """数据对本次区域和时间范围的实际覆盖情况。"""

    FULL = "full"  # 全部覆盖。
    PARTIAL = "partial"  # 只覆盖一部分。
    NONE = "none"  # 确认没有覆盖。
    UNKNOWN = "unknown"  # 尚未检查或无法确认。


class MissingPolicy(str, Enum):
    """缺少变量时怎么处理；一个变量可按先后顺序设置多种办法。"""

    BLOCK = "block"  # 停止依赖该变量的分析。
    ESTIMATE = "estimate"  # 用明确方法估算，并降低可信程度。
    PROXY = "proxy"  # 改用相关数据作近似参考。
    MASK = "mask"  # 不分析缺少数据的空间范围。
    UNKNOWN = "unknown"  # 保留为未知，不猜测对象是否存在。
    REQUIRE_TASK_INPUT = "require_task_input"  # 要求任务方补充设置。
    RECONNAISSANCE_REQUIRED = "reconnaissance_required"  # 输出需要补充观察的事项。


class ImpactLevel(str, Enum):
    """变量缺失对其直接分析结果的影响。"""

    HIGH = "high"  # 可能无法计算，或会明显改变结论。
    MEDIUM = "medium"  # 可以继续，但结果会有明显限制。
    LOW = "low"  # 主要影响细节，对主体结果影响较小。


class ConfidenceLevel(str, Enum):
    """用四个等级表示结果可信程度。"""

    HIGH = "high"  # 证据充分且质量达到要求。
    MEDIUM = "medium"  # 证据基本可用，但存在部分限制。
    LOW = "low"  # 证据不足，只适合谨慎参考。
    UNKNOWN = "unknown"  # 还没有足够信息作出判断。


class AccessMethod(str, Enum):
    """公开数据服务提供的查询或下载方式。"""

    STAC = "stac"  # 先按区域、时间和产品检索，再读取数据文件地址。
    ODATA = "odata"  # 通过带筛选条件的网页接口查询产品。
    S3 = "s3"  # 从对象存储中读取文件。
    HTTPS = "https"  # 通过普通网页地址下载。
    OVERPASS = "overpass"  # 按区域和标签查询 OpenStreetMap 对象。
    PBF_DOWNLOAD = "pbf_download"  # 下载压缩的 OpenStreetMap 区域数据包。
    REST = "rest"  # 通过普通接口请求数据。
    WCS = "wcs"  # 按空间范围请求网格数据。
    CDS_API = "cds_api"  # 通过 Copernicus Climate Data Store 接口下载。


class VerificationStatus(str, Enum):
    """公开服务信息核实到什么程度，待确认内容不能当成已实现能力。"""

    VERIFIED = "verified"  # 主要入口和能力已经核实。
    PARTIAL = "partial"  # 只核实了部分入口或字段。
    PENDING = "pending"  # 还需要实际访问测试。


class TimeWindow(BaseModel):
    """任务结果适用的时间范围；只写开始或只写结束也可以。"""

    start_at: datetime | None = None  # 最早有效时间。
    finish_by: datetime | None = None  # 最晚有效时间。

    # 模型字段转换完成后，再检查开始和结束之间的关系。
    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        # 两个时间都不写就无法确定结果何时有效，因此拒绝该输入。
        if self.start_at is None and self.finish_by is None:
            raise ValueError("时间窗口至少需要一个边界")
        # 两个时间都存在时，结束时间必须排在开始时间之后。
        if self.start_at and self.finish_by and self.finish_by <= self.start_at:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class VersionedReference(BaseModel):
    """用编号和版本指向一份规则或能力设置，避免后续不知道用了哪一版。"""

    id: str = Field(min_length=1)  # 系统中保持不变的编号。
    version: str = Field(min_length=1)  # 本次执行使用的明确版本。


class AreaOfInterest(BaseModel):
    """要分析的地图范围，可以直接写 GeoJSON，也可以填写外部文件地址。"""

    id: str = Field(min_length=1)  # 本次任务用来引用该分析区域的编号。
    name: str = Field(min_length=1)  # 面向人员展示的区域名称。
    geometry: dict[str, JsonValue] | None = None  # GeoJSON Polygon 或 MultiPolygon。
    uri: str | None = None  # 外部 GeoJSON、GeoPackage 或数据库对象引用。
    crs: str = Field(min_length=1)  # 坐标使用的地图坐标系，必须明确填写。

    # 区域至少需要一种来源，而且直接填写的内容必须是面。
    @model_validator(mode="after")
    def validate_geometry_source(self) -> Self:
        # geometry 和 uri 都为空时，程序不知道实际要分析哪里。
        if self.geometry is None and self.uri is None:
            raise ValueError("AOI 必须提供 geometry 或 uri")
        # OAKOC 分析针对一个范围，因此这里不接受点或线。
        if self.geometry is not None and self.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("AOI geometry 必须是 GeoJSON Polygon 或 MultiPolygon")
        return self


class MissionInput(BaseModel):
    """说明任务要达到什么目的，后续关键地形和路线判断都要以此为准。"""

    name: str = Field(min_length=1)  # 任务名称。
    objective: str = Field(min_length=1)  # 可验证的任务目的。
    desired_end_state: str = Field(min_length=1)  # 期望形成的状态。
    phase: str = Field(min_length=1)  # 任务当前处于哪个阶段，具体选项由任务方规定。


class ActorInput(BaseModel):
    """说明分析是针对谁进行的，因为同一地形对不同主体的影响并不相同。"""

    id: str = Field(min_length=1)  # 供结果范围和能力配置引用。
    name: str = Field(min_length=1)  # 面向人员展示的名称。
    side: Literal["friendly", "opposing", "neutral"]  # 分析视角中的阵营。


class DataAsset(BaseModel):
    """登记本次取得的数据文件或地址；大文件本身不放进请求内容。"""

    id: str = Field(min_length=1)  # 本次运行内唯一资产标识。
    source_id: str | None = None  # 对应公开来源目录中的编号；任务自带数据可不填。
    name: str = Field(min_length=1)  # 数据资产名称。
    kind: Literal["terrain", "facility", "weather", "imagery", "observation", "other"]  # 保存资产类别。
    uri: str = Field(min_length=1)  # 本地、对象存储或远程资产地址。
    media_type: str | None = None  # GeoTIFF、PBF、GeoParquet 等实际格式。
    crs: str | None = None  # 资产声明的坐标参考系。
    version: str | None = None  # 产品版本或快照版本。
    license: str | None = None  # 发布时需要保留的许可证标识。
    observed_at: datetime | None = None  # 数据代表的观测时间。
    retrieved_at: datetime | None = None  # 系统取得资产的时间。
    checksum: str | None = None  # 文件内容校验值，用来确认后来读取的是同一份文件。
    variable_ids: list[str] = Field(default_factory=list)  # 该数据实际可以提供哪些变量。


class EnvironmentInput(BaseModel):
    """把分析区域和本次已经取得的数据放在一起。"""

    analysis_area: AreaOfInterest  # 具有明确 CRS 的面几何或外部资产引用。
    assets: list[DataAsset] = Field(default_factory=list)  # 保存已经取得的数据资产。


class AnalysisControl(BaseModel):
    """控制本次分析怎样运行，包括视角、规则、时间和能力设置。"""

    analysis_perspective: str = Field(min_length=1)  # 适用主体或阵营 ID。
    rule_set: VersionedReference  # 记录本次判断使用哪一版规则和数值界限。
    target_crs: str | None = None  # 希望统一到的地图坐标系；不填时根据输入数据选择。
    analysis_resolution_m: float | None = Field(default=None, gt=0)  # 目标栅格分辨率。
    time_windows: list[TimeWindow] = Field(min_length=1)  # 静态和动态结果的有效时间。
    # 默认执行全部六项分析，调用方也可以只选择其中一部分。
    requested_analyses: list[AnalysisKind] = Field(default_factory=lambda: list(AnalysisKind))
    platform_profiles: list[VersionedReference] = Field(default_factory=list)  # 机动分析配置。
    sensor_profiles: list[VersionedReference] = Field(default_factory=list)  # 观察分析配置。
    fire_profiles: list[VersionedReference] = Field(default_factory=list)  # 射界分析配置。
    task_constraints: list[str] = Field(default_factory=list)  # 保存禁行区和时间限制等任务条件。
    route_terminals: RouteControlPoints | None = None  # 保存接近路线的起点和终点。


class AnalysisRequest(BaseModel):
    """完整运行请求；不同来源的数据最后都要整理成这一格式。"""

    mission: MissionInput  # 任务目的与阶段。
    actors: list[ActorInput] = Field(min_length=1)  # 至少存在一个分析主体。
    environment: EnvironmentInput  # 分析区域与已经取得的数据。
    control: AnalysisControl  # 规则版本、时间和能力参数。


class QualityRequirement(BaseModel):
    """目录中预先写明的数据质量要求，本次数据是否达到要求要运行时再检查。"""

    minimum_coverage_ratio: float | None = Field(default=None, ge=0, le=1)  # 保存最低覆盖率。
    target_resolution_m: float | None = Field(default=None, gt=0)  # 保存目标空间分辨率。
    maximum_age_hours: float | None = Field(default=None, ge=0)  # 保存允许的数据时效。
    checks: tuple[str, ...] = ()  # 例如坐标系、空白区域、地图对象连接和时间是否一致。


class ConfidenceAssessment(BaseModel):
    """说明结果大致可信到什么程度，并列出提高或降低判断的原因。"""

    level: ConfidenceLevel  # 面向使用者的离散等级。
    evidence_coverage: float | None = Field(default=None, ge=0, le=1)  # 保存证据覆盖比例。
    reasons: list[str] = Field(default_factory=list)  # 降低或无法判定的原因。


class QualityAssessment(BaseModel):
    """记录本次实际拿到的某项数据质量如何。"""

    variable_id: str = Field(min_length=1)  # 被评价变量。
    asset_ids: list[str] = Field(default_factory=list)  # 本次质量检查使用了哪些数据。
    coverage_status: CoverageStatus  # 当前 AOI 和时间窗的覆盖结论。
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)  # 保存实际覆盖率。
    spatial_resolution_m: float | None = Field(default=None, gt=0)  # 保存实际空间分辨率。
    observed_at: datetime | None = None  # 数据代表时间，用于计算时效。
    assessed_at: datetime  # 质量检查执行时间。
    flags: list[str] = Field(default_factory=list)  # 数据空白、过期或地图对象连接错误等问题。
    confidence: ConfidenceAssessment  # 保存质量判断的可信程度。


class VariableSpec(BaseModel):
    """说明一个变量是什么、从哪里来、缺少时怎么办以及后面哪里会使用。"""

    variable_id: str = Field(pattern=r"^[a-z][a-z0-9_.]*$")  # 程序中保持不变的英文编号。
    name_zh: str = Field(min_length=1)  # 精确中文业务名称。
    description: str = Field(min_length=1)  # 变量在真实业务中的含义。
    stage: StageId  # 第一次要求或计算出该变量的步骤。
    data_role: DataRole  # 它是任务背景、地图数据、运行设置还是分析结果。
    value_type: ValueType  # 内容属于文字、数值、点、线、面还是网格等类型。
    unit: str | None = None  # 无量纲或对象引用可为空。
    requirement_level: RequirementLevel  # 业务必要性。
    required_when: str | None = None  # 条件必要变量的触发说明。
    implementation_priority: ImplementationPriority  # 第一版实现优先级。
    accessibility: Accessibility  # 通常能直接取得、计算得到、只能近似还是无法取得。
    acquisition_modes: tuple[AcquisitionMode, ...]  # 允许的获取途径。
    result_impact: ImpactLevel  # 缺失对直接结果的影响。
    source_priority: tuple[str, ...] = ()  # 可用公开来源的编号，越靠前越优先。
    source_fields: dict[str, str] = Field(default_factory=dict)  # 已核实源字段或波段。
    depends_on: tuple[str, ...] = ()  # 计算这个变量前必须已有的变量编号。
    derivation: str | None = None  # 说明大致计算办法，具体公式和数值以后由规则版本确定。
    quality_requirement: QualityRequirement = Field(default_factory=QualityRequirement)  # 保存质量要求。
    missing_policies: tuple[MissingPolicy, ...]  # 按顺序保存缺失处理方法。
    used_by: tuple[StageId, ...]  # 保存使用该变量的阶段。


class VariableBinding(BaseModel):
    """记录本次运行是否真正取得了变量，以及它的值或数据文件在哪里。"""

    variable_id: str = Field(min_length=1)  # 对应变量目录中的哪个变量。
    status: AvailabilityStatus  # 实际可用状态。
    acquisition_mode: AcquisitionMode  # 本次采用的取得方式。
    value: JsonValue | None = None  # 小型配置值；大数据只保存 asset_ids。
    asset_ids: list[str] = Field(default_factory=list)  # 提供该变量的数据编号。
    quality: QualityAssessment | None = None  # 获取后形成的质量结论。
    limitations: list[str] = Field(default_factory=list)  # 对结果使用的明确限制。


class RequirementManifest(BaseModel):
    """第一步根据任务内容整理出的本次变量需求清单。"""

    run_id: str = Field(min_length=1)  # 本次运行编号，从第一步到发布都保持不变。
    catalog_version: str = Field(min_length=1)  # 变量目录版本。
    required_variable_ids: list[str]  # 保存本次运行需要的变量 ID。
    unresolved_variable_ids: list[str] = Field(default_factory=list)  # 待获取或补录变量。
    # 正式运行时应因缺少数据而停止的步骤。
    blocked_stages: list[StageId] = Field(default_factory=list)
    generated_at: datetime  # 需求清单生成时间。


class SourceSpec(BaseModel):
    """说明一个公开数据服务能提供什么、怎样访问以及有哪些已知限制。"""

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_.]*$")  # 稳定来源标识。
    provider: str = Field(min_length=1)  # 数据提供组织。
    dataset: str = Field(min_length=1)  # 产品或数据库名称。
    access_methods: tuple[AccessMethod, ...]  # 保存服务支持的访问方式。
    discovery_url: str = Field(min_length=1)  # 官方目录或服务入口。
    coverage: str = Field(min_length=1)  # 官方说明的覆盖范围，不代表本次区域一定完整。
    resolution: str = Field(min_length=1)  # 官方标称或明确的量级描述。
    temporal_coverage: str = Field(min_length=1)  # 数据代表的时间范围。
    update_frequency: str = Field(min_length=1)  # 更新节奏或静态版本说明。
    authentication: str = Field(min_length=1)  # 注册、令牌或匿名要求。
    license: str = Field(min_length=1)  # 许可证或使用条款名称。
    provides: tuple[str, ...]  # 保存来源能够直接提供的变量 ID。
    calculable_formats: tuple[str, ...]  # 程序能够读取并用于计算的文件格式。
    limitations: tuple[str, ...]  # 保存来源的已知限制。
    fallback_source_ids: tuple[str, ...] = ()  # 备用来源优先序。
    # 后续负责查询和下载该来源的代码名称，目前不代表已经实现。
    adapter: str = Field(min_length=1)
    verification_status: VerificationStatus  # 服务能力核实状态。
    verified_on: date | None = None  # 最近核实日期。
    verification_note: str = Field(min_length=1)  # 已核实与仍待确认的边界。


class PreparedContext(BaseModel):
    """数据准备步骤形成的统一输入，后面的六项分析都从这里读取数据。"""

    request: AnalysisRequest  # 原始标准请求。
    requirement_manifest: RequirementManifest  # 本次运行变量需求。
    canonical_crs: str | None = None  # 本次所有地图数据统一采用的坐标系。
    variable_bindings: list[VariableBinding] = Field(default_factory=list)  # 已取得的变量值和数据编号。
    quality_issues: list[str] = Field(default_factory=list)  # 便于人员直接阅读的数据问题摘要。


class ResultScope(BaseModel):
    """所有分析结果必须声明的适用范围。"""

    analysis_area: str = Field(min_length=1)  # AOI 引用。
    perspective: str = Field(min_length=1)  # 适用主体或阵营。
    valid_time: list[TimeWindow] = Field(min_length=1)  # 适用时间条件。
    rule_set: VersionedReference  # 使用的规则版本。


class AnalysisFinding(BaseModel):
    """一条带证据来源和适用范围的分析判断，不能写成无条件的绝对结论。"""

    title: str = Field(min_length=1)  # 判断标题。
    assessment: str = Field(min_length=1)  # 带适用条件的结论文本。
    areas: list[str] = Field(default_factory=list)  # 空间对象或结果图层引用。
    evidence_source_ids: list[str] = Field(default_factory=list)  # 证据来源 ID。


class AnalysisResult(BaseModel):
    """六项分析共用的结果格式，具体地图字段以后随算法实现再补充。"""

    kind: AnalysisKind  # 结果对应的分析节点。
    scope: ResultScope  # 主体、时间、区域和规则版本。
    status: AvailabilityStatus  # 完整、部分、降级或不可用。
    summary: str = Field(min_length=1)  # 不超出证据能力的结果摘要。
    findings: list[AnalysisFinding] = Field(default_factory=list)  # 可追踪判断。
    warnings: list[str] = Field(default_factory=list)  # 缺口及使用限制。
    confidence: ConfidenceAssessment  # 这项分析整体的可信程度。
    placeholder: bool = False  # 防止框架占位结果进入正式发布。


class StageRecord(BaseModel):
    """记录每一步何时开始、何时结束以及是否成功，便于查找问题。"""

    stage: StageId  # 十三阶段之一。
    status: StageStatus  # 执行结果。
    started_at: datetime  # 阶段开始时间。
    completed_at: datetime  # 阶段结束时间。
    message: str = ""  # 降级、失败或完成摘要。


class PublishedOutput(BaseModel):
    """列出最终应该发布哪些成果；实际地图和文件由后续发布代码生成。"""

    map_products: list[str] = Field(default_factory=list)  # 地图产品引用或待生成项。
    structured_sections: list[AnalysisKind] = Field(default_factory=list)  # 结构化结果章节。
    data_gap_report: list[str] = Field(default_factory=list)  # 必要变量缺口。
    conclusion: str  # 保存带限制条件的综合说明。
    warnings: list[str] = Field(default_factory=list)  # 发布层限制。


class PipelineResult(BaseModel):
    """一次完整运行的总结果，包括输入准备、十三步记录、分析结果和发布内容。"""

    run_id: str = Field(min_length=1)  # 与 RequirementManifest 保持一致。
    mode: Literal["demo", "production"]  # demo 允许占位结果。
    status: RunStatus  # 成功、降级或失败。
    context: PreparedContext  # 已经整理过、供分析函数使用的统一输入。
    stages: list[StageRecord]  # 十三个步骤各自的执行记录。
    analyses: list[AnalysisResult]  # 保存六个计算节点的结果。
    validation_issues: list[str] = Field(default_factory=list)  # 综合校验问题。
    output: PublishedOutput  # 最终成果索引。
