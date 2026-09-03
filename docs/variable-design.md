# OAKOC 全流程变量设计

本文是代码目录的开发说明。变量的完整机器可读定义以 `oakoc/catalog.py` 为准，本文不重复每个字段，而是按执行步骤解释业务目的、MVP 输入输出、公开数据能力和缺失行为。

## 设计原则

十三步不等于十三套业务类。每一步保留独立阶段 ID，是因为数据获取、标准化、质量检查和派生的失败原因、重试边界及血缘完全不同；实现仍归并为五个执行组。

变量按以下独立维度筛选：

| 设计问题 | 对应字段 |
|---|---|
| 是否为业务所必需 | `requirement_level`、`required_when` |
| 第一版何时实现 | `implementation_priority` |
| 如何取得 | `accessibility`、`acquisition_modes` |
| 当前任务是否真的取得 | `VariableBinding.status` |
| 当前 AOI 是否完整覆盖 | `QualityAssessment.coverage_status` |
| 缺失如何处理 | 有序 `missing_policies` |

质量不是普通变量角色，而是所有运行时数据绑定和结果的横切元数据。分析结果必须携带 AOI、适用主体、时间窗、规则版本、来源和结构化置信度。

## 逐步变量

### 1. `context.requirements`

目标：从任务目的和请求分析项反向生成本次运行的变量需求，不假定全部目录变量都必需。

| 类别 | MVP 变量 |
|---|---|
| 必要且任务侧可提供 | `context.aoi`、`context.time_window`、`context.analysis_perspective`、`context.mission_phase`、`context.mission_objective`、`context.requested_analyses`、`context.rule_set_ref` |
| 条件必要且任务侧可提供 | `context.effect_criteria`、`parameter.mobility_profile`、`parameter.sensor_profile`、`context.route_terminals` |
| 条件必要但公开不可得 | `parameter.fire_profile`，必须由任务侧提供 |
| 可选且易提供 | `context.task_constraints`、`parameter.target_crs`、`parameter.analysis_resolution` |

输出 `RequirementManifest`，包括已触发需求、未绑定变量和受阻阶段。AOI 必须是带 CRS 的 Polygon/MultiPolygon 或外部几何资产引用；不能只保存模糊地名。

### 2. `data.acquire`

目标：将公开数据、任务数据和现场观测转换为可追踪 `DataAsset` 与 `VariableBinding`，不在获取阶段直接生成业务判断。

| 优先级 | 变量 | 主要渠道 | 缺失影响 |
|---|---|---|---|
| P0 | `raster.elevation` | Copernicus DEM GLO-30 | 高；坡度和几何视线无法可靠计算 |
| P0 | `raster.land_cover` | ESA WorldCover | 高；地表和植被代理不足 |
| P0 条件必要 | `entity.transport_network` | Overpass，小 AOI；Geofabrik PBF，大 AOI | 高；路线网络和桥隧识别不完整 |
| P0 条件必要 | `entity.hydrography` | OSM，HydroRIVERS 作区域补充 | 高；水障碍候选不完整 |
| P1 | `entity.buildings` | OSM | 中；城市遮挡与建设区代理降低 |
| P1 | `raster.surface_water_history` | JRC Global Surface Water | 中；历史水体证据减少 |
| P1 | `raster.optical_imagery`、`raster.sar_imagery` | Sentinel-2 L2A、Sentinel-1 GRD | 中；近期地表变化代理减少 |
| P1 | `raster.soil_properties` | SoilGrids | 中；土壤承载代理减少 |
| P1 | `raster.weather_fields` | ERA5-Land | 中；只可提供约 9 km 背景气象 |

公开数据通常无法可靠提供桥梁承载与损毁、实时水文、局地能见度、临时障碍、建筑防护属性和精确冠层结构。第一版只保留前三项必要接口；其余内容写入结果限制，等有明确数据来源时再建模。高影响缺失应保留 `UNKNOWN`，不能用“对象不存在”替代。

### 3. `data.normalize`

目标：统一 CRS、垂直基准、AOI、时间、单位、分类编码和 NoData 语义。

必要输出为 `derived.normalized_data_stack` 和 `derived.data_coverage_mask`。覆盖掩膜必须区分完整、部分、无覆盖和未知；重采样不能制造比源数据更高的事实精度。

### 4. `data.quality_and_derive`

目标：测量实际覆盖、分辨率、时效和内容质量，并生成跨五项分析复用的公共地形变量。

| 类型 | MVP 变量 | 说明 |
|---|---|---|
| 必要派生 | `derived.slope` | DEM 派生；坡度不直接等于不可通行 |
| 必要派生 | `derived.base_mobility_surface` | 对齐坡度、覆盖、路网和水系证据，尚未套用平台结论 |
| 必要质量 | `result.data_quality_report` | 逐变量记录来源、覆盖、时效、分辨率和问题 |
| 条件必要 | `derived.hydrologic_barriers` | 静态水系、历史水体和实时观测分层融合 |
| 条件必要 | `derived.surface_height_model` | 缺少建筑/冠层高度时只能退化为 DEM 并标记 |
| P1 增强 | `derived.aspect`、`derived.terrain_roughness`、`derived.vegetation_density_proxy`、`derived.built_up_density` | 增强解释能力，不替代现场属性 |

### 5. `baseline.build`

目标：组装 `result.analysis_baseline` 和逐分析节点的 `result.baseline_readiness`。基线包含变量绑定、质量、覆盖掩膜、规则版本和未知区，不产生障碍、可视域或关键地形结论。

### 6. `analysis.obstacles`

目标：针对明确 `mobility_profile` 和时间窗解释机动影响。

输入重点为 `derived.base_mobility_surface`、动态状况、桥梁状态、水文状态和临时障碍；输出 `result.obstacle_zones`、`result.mobility_cost_surface` 和 `result.mobility_restrictions`。无法核实桥梁或渡越状态时，路线单元保持未知并生成补采需求，不能默认可通过或不可通过。

### 7. `analysis.observation_and_fire`

目标：区分几何通视、实际探测条件和条件射界。

`result.viewshed` 依赖表面高度模型和传感器配置；`result.observation_gaps` 区分几何盲区、天气限制和数据未知区。`result.fire_coverage`、`result.fire_dead_zones` 只有在任务侧提供版本化 `fire_profile` 时才可计算，公开地形数据不能补出火力能力。

### 8. `analysis.cover_and_concealment`

目标：相对于指定观察或作用威胁形成 `result.cover_zones`、`result.concealment_zones` 和 `result.exposure_surface`。

建筑轮廓与建设区密度不能证明结构防护能力；土地覆盖和光学植被指标不能证明冠层高度或树干间距。代理结果必须降级并记录限制。

### 9. `analysis.foundation_aggregate`

目标：把三项基础分析统一为 `result.foundation_evidence_stack`，并输出 `result.foundation_conflicts`。汇聚只统一范围、分辨率、状态和引用，不覆盖原组件置信度，也不使用单一总分掩盖冲突。

### 10. `analysis.key_terrain_candidates`

目标：使用任务目的、效果判据和基础证据形成 `result.key_terrain_candidates` 与 `result.candidate_control_effects`。这些只是候选，必须保留入选证据和适用主体，不能在路线分析前称为最终关键地形。

### 11. `analysis.approach_routes`

目标：从任务起终区域、机动成本、暴露面和候选关键地形生成多条候选路线。

输出 `result.approach_routes`、`result.route_cost_profiles`、`result.route_chokepoints`，条件允许时输出 `result.route_windows`。成本剖面必须分列距离、机动、暴露、时间和未知成本；UNKNOWN 不能作为零成本参与最短路。

### 12. `analysis.key_terrain_review`

目标：用路线依赖、瓶颈、替代性和候选控制效果复核关键地形，输出 `result.key_terrain_review` 和 `result.key_terrain_route_relevance`。未通过复核及无法确认的候选同样需要保留原因。

### 13. `publish.validate_and_release`

目标：输出 `result.data_gap_report`、`result.map_products`、`result.structured_package` 和 `result.analysis_conclusion`。

正式发布必须拒绝占位结果和阻断级必要变量缺失。降级结果可以保留，但地图、结构化结果和结论都必须明确主体、AOI、时间窗、规则版本、来源、置信度和限制。

## 公开服务获取链路

所有来源遵循同一过程：

```text
SourceSpec 登记
→ 按 AOI、时间窗、产品级别和许可证检索目录
→ 选择可计算资产并记录产品版本
→ 下载或挂载 GeoTIFF/COG、PBF、GeoJSON、GeoParquet、GRIB/NetCDF
→ 校验校验和、CRS、覆盖、NoData、时间和内容字段
→ 形成 VariableBinding 与 QualityAssessment
→ 应用 BLOCK/MASK/PROXY/UNKNOWN/补采策略
```

WMS/WMTS 适合展示，不作为主要计算输入。STAC 和 OData 负责发现资产，不表示资产已经下载、授权或覆盖本次 AOI。

## 来源能力边界

| 来源 | 已登记访问方式 | 直接证据 | 明确不能直接提供 |
|---|---|---|---|
| Copernicus DEM | OData、S3、HTTPS | 高程 | 建筑/冠层高度、实时地形状态 |
| ESA WorldCover | HTTPS 资产 | 10 m 土地覆盖分类 | 冠层结构、土壤强度、实时变化 |
| Sentinel-1 GRD | CDSE STAC、OData、S3 | 雷达影像与元数据 | 已确认积水或障碍状态 |
| Sentinel-2 L2A | CDSE STAC、OData、S3 | 表面反射率与场景分类 | 无云保证、真实通行性 |
| OSM Overpass | Overpass API | 道路、建筑、水系及现有标签 | 数据完整性、桥梁承载、实时损毁 |
| Geofabrik | 区域 PBF 下载 | OSM 批量快照 | AOI 精确裁剪、标签完整性 |
| SoilGrids 2.0 | REST、WCS/下载待适配器验收 | 250 m 土壤属性预测 | 实时含水量和平台承载结论 |
| HydroRIVERS | 区域下载包 | 区域尺度河网 | 局地河宽、水深、流速、岸坡 |
| JRC Surface Water | HTTPS、Earth Engine | 30 m 历史水体统计 | 当前水文状态和可渡性 |
| ERA5-Land | CDS API | 约 9 km 背景气象 | 战术尺度局地天气和能见度 |

`SourceSpec.verification_status` 表示当前接口登记的核实程度。`PENDING` 或 `PARTIAL` 的下载 URL、collection ID、许可流程和服务限制必须在实现适配器时做验收测试。

## 第一版范围

MVP 优先实现：任务上下文、DEM、土地覆盖、OSM 交通/水系、质量与覆盖掩膜、坡度、基础机动证据、六个分析器接口、数据缺口和完整追踪信息。

保留接口但暂缓形成正式事实：精确桥梁承载与实时损毁、实时水深流速和河床、临时人工障碍、建筑材料与抗毁能力、精确冠层结构、高分辨率实时局地能见度。它们不能从目录删除，因为其缺失会实质影响分析；第一版应输出未知、限制或补采需求。
