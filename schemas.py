from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Literal, Annotated


class TimeWindow(BaseModel):
    start_at: datetime | None = None  # 最早开始时间
    finish_by: datetime | None = None  # 最迟完成时间

    @model_validator(mode="after")
    def check_time(self) -> Self:
        if self.start_at is None and self.finish_by is None:
            raise ValueError("时间窗口至少需要一个时间边界")
        if self.start_at and self.finish_by and self.finish_by <= self.start_at:
            raise ValueError("完成时间必须晚于开始时间")
        return self

class Position(BaseModel):
    name: str | None = None  # 普通边界点不一定有名称
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    elevation_m: float | None = None  # 相对平均海平面的地面高程

class Area(BaseModel):
    name: str = Field(min_length=1)  # 任务地域名称
    boundary: list[Position] | None = Field(default=None, min_length=3)  #  任务边界



class SuperiorMission(BaseModel):
    purpose: str = Field(min_length=1)  # 上级行动目的
    desired_end_state: str = Field(min_length=1)  # 上级期望的最终状态
    time_window: TimeWindow | None = None  #  时间窗口
    area: Area  #  任务地域
    restrictions: list[str] = Field(default_factory=list)  #  限制条件
    available_resources: list[str] = Field(default_factory=list)  #  资源关系
    coordination: list[str] = Field(default_factory=list)  #  协同约束


class OwnMission(BaseModel):
    executor: str = Field(min_length=1)  # 谁
    action: str = Field(min_length=1)  # 做什么
    target: str = Field(min_length=1)  # 对谁或对什么行动
    time_window: TimeWindow | None = None  # 何时
    area: Area  # 何地
    purpose: str = Field(min_length=1)  # 为什么
    required_state: str = Field(min_length=1)  # 完成后必须形成的状态


class MainProblem(BaseModel):
    task_gap: str = Field(min_length=1)  # 当前状态与本级任务之间的任务差距
    enemy_support_mechanisms: list[str] = Field(default_factory=list)  #  敌方的支撑机制
    own_key_limitations: list[str] = Field(default_factory=list)  #  我方的条件限制


class DecisiveCondition(BaseModel):
    subject: str = Field(min_length=1,description="作用对象") 
    required_state: str = Field(min_length=1,description="必须形成的可观察状态") 
    time_window: list[TimeWindow] | None = Field(default=None,description="必须在这些时间窗口内完成")  #  必须在这些时间窗口内完成
    area: Area = Field(description="地域信息")
    indicators: list[str] = Field(min_length=1,description="判断状态是否形成的依据")

def DecisiveConditionResult() -> DecisiveCondition:
    return DecisiveCondition(
    subject="首尔地区主要交通分配体系",
    required_state= "控制关键交通枢纽，切断朝军南北补给线，使得朝军无法继续维持釜山正面攻势",
    time_window=[
        TimeWindow(
            start_at = datetime(1950,9,15,6,30),
            finish_by = datetime(1950,9,15,8,0),
        ),
        TimeWindow(
            start_at = datetime(1950,9,15,17,30),
            finish_by = datetime(1950,9,16,12,00),
        )
    ],
    area = Area(
        name = "法定仁川港水域",
        boundary= [
        Position(name="P01 法定控制点", longitude=126.59948056, latitude=37.54717778, elevation_m=0.0),
        Position(name="P02 金浦市阳村面", longitude=126.56904722, latitude=37.59334722, elevation_m=0.0),
        Position(name="P03 永宗岛北端", longitude=126.51460833, latitude=37.53446389, elevation_m=0.0),
        Position(name="P04 永宗岛南端", longitude=126.48627778, latitude=37.44641944, elevation_m=0.0),
        Position(name="P05 大阜岛西北端驼九峰端点", longitude=126.53294167, latitude=37.28865833, elevation_m=0.0),
        ],
    ),
    indicators= [
        "控制首尔地区交通枢纽和南北关键通道",
        "朝军正面无法维持攻势，开始后撤"
    ]
)

decisive_res = DecisiveConditionResult()

class ObservationAndFire(BaseModel):
    "观察与射界"
    observed_area: Area = Field(description="能够观察到的完整区域")  
    fire_coverage: Area | None = Field(default=None,description="火力覆盖到的区域") 
    
    disadvantage_area: Area | None = Field(default=None,description="火力覆盖不到的死角区域")
    limiting_conditions: dict[Literal["observation","fire"],str] = Field(description="观察和火力的限制条件")
    effect_on_approach: dict[Literal["observation","fire"],str] = Field(description="观察和火力的总体影响") 

class ApproachRoute(BaseModel):
    "接近路"
    route: Annotated[list[Area],Field(min_length=2,description="通行路径所经过的区域")]
    available_windows: dict[str,list[TimeWindow]] | None = Field(default=None,description="通行该区域的时间窗口")
    conditions: dict[Literal["movement","timing","continuity"],str] = Field(description="通行需要面对的限制条件") # 通行限制条件
    access_effect: str = Field(min_length=1,description="接近路能够达到的效果")  

class KeyTerrain(BaseModel):
    "关键地形"    
    key_area: Area = Field(description="关键地形的区域信息") 
    affected_area: Area | None = Field(default=None,description="受关键地形影响的区域") # 受关键地形影响区域
    control_effects: dict[Literal["friendly","enemy"],str] = Field(description="控制关键地形对敌我双方的影响") # 控制关键地形后产生的影响
    relevance: dict[Literal["mission","approach"],str] = Field(min_length=1,description="与任务和接近路的关系")  # 与任务和接近路的关系

class Obstacle(BaseModel):
    "障碍"
    name: str = Field(min_length=1,description="障碍的名字") 
    kind: Literal["natural","artificial"] = Field(description="障碍类型，分自然和人工两种") 
    obstacle_area: Area = Field(description="障碍的位置信息") 
    movement_effect: dict[Literal["passage","deployment"],str] = Field(min_length=1,description="障碍对通过和展开的影响")
    passage_requirements: list[str] = Field(min_length=1,description="通过障碍所需条件")  

class CoverAndConcealment(BaseModel):
    "遮蔽与隐蔽"
    cover_area: Area | None = Field(default=None,description="能够掩蔽，存在掩体的区域") 
    concealment_area: Area | None = Field(default=None,description="能够隐蔽，隐藏自身的区域") 
    threats: dict[Literal["fire","observation"],str] = Field(description="掩蔽和隐蔽区域所需应对的威胁")
    effective_conditions: dict[Literal["cover","concealment"],str] = Field(default_factory=dict,description="掩蔽和隐蔽生效的条件") # 掩蔽和隐蔽区域的生效条件
    limitations: dict[Literal["cover","concealment"],str] = Field(default_factory=dict,description="掩蔽和隐蔽区域的局限性")  # 掩蔽和隐蔽区域的局限

class OAKOCResult(BaseModel):
    "OAKOC的完整分析结果"
    approach: ApproachRoute
    observation_and_fire: list[ObservationAndFire]
    key_terrain: list[KeyTerrain]
    obstacles: list[Obstacle]
    cover_and_concealment: list[CoverAndConcealment]

def build_inchon_oakoc_result() -> OAKOCResult:
    "根据仁川实例化OAKOC的结果"
    return OAKOCResult(
        approach=ApproachRoute(
            route=[
                Area(name="黄海海上集结地域"),
                Area(name="飞鱼航道"),
                Area(name="月尾岛近岸与仁川港入口"),
                Area(name="仁川港红滩和蓝滩"),
                Area(name="仁川—金浦—首尔交通走廊"),
            ],
            available_windows={
                "月尾岛登陆计划窗口": [
                    TimeWindow(
                        start_at=datetime(1950, 9, 15, 6, 30),
                        finish_by=datetime(1950, 9, 15, 8, 0),
                    )
                ],
                "仁川港主登陆计划窗口": [
                    TimeWindow(
                        start_at=datetime(1950, 9, 15, 17, 30),
                        finish_by=datetime(1950, 9, 15, 20, 0),
                    )
                ],
            },
            conditions={
                "movement": (
                    "大型舰艇需沿狭窄弯曲的飞鱼航道接近；低潮时浅滩和泥滩"
                    "限制舰艇靠岸及登陆艇运动"
                ),
                "timing": "航道通行和越过岸滩、海堤的行动必须配合高潮窗口",
                "continuity": (
                    "飞鱼航道、仁川港入口、登陆岸滩、港区出口以及"
                    "仁川至首尔道路必须依次保持可通行"
                ),
            },
            access_effect=(
                "使登陆力量能够由海上进入仁川港，建立岸上入口，"
                "并沿金浦方向接近首尔地区交通体系"
            ),
        ),
        observation_and_fire=[
            ObservationAndFire(
                observed_area=Area(name="飞鱼航道末段、仁川港入口及邻近岸滩"),
                fire_coverage=Area(name="月尾岛周边水道、仁川港入口及红滩方向"),
                disadvantage_area=Area(
                    name="月尾岛背坡及港区建筑遮挡形成的视线受限地域"
                ),
                limiting_conditions={
                    "observation": "月尾岛地形起伏、港区建筑和烟尘会造成观察中断",
                    "fire": "岛体遮挡、港区建筑和狭窄水道限制部分火力射界",
                },
                effect_on_approach={
                    "observation": (
                        "控制月尾岛的一方能够监视飞鱼航道末段、"
                        "港口入口及部分登陆岸滩"
                    ),
                    "fire": (
                        "月尾岛及港区防御火力能够威胁进入港口的舰艇、"
                        "登陆艇和岸滩出口"
                    ),
                },
            ),
            ObservationAndFire(
                observed_area=Area(name="仁川港岸滩、海堤出口及港区主要道路"),
                fire_coverage=Area(name="仁川港海堤、红滩、蓝滩及港区道路入口"),
                disadvantage_area=Area(name="港区建筑背后及街巷转折地域"),
                limiting_conditions={
                    "observation": "密集建筑限制远距离连续观察",
                    "fire": "建筑和狭窄街道分割射界，火力难以覆盖全部港区",
                },
                effect_on_approach={
                    "observation": "岸滩出口和主要道路容易受到近距离观察",
                    "fire": "海堤出口和主要街道可能形成限制登陆力量展开的火力通道",
                },
            ),
        ],
        key_terrain=[
            KeyTerrain(
                key_area=Area(name="月尾岛"),
                affected_area=Area(name="飞鱼航道末段、仁川港入口及红滩"),
                control_effects={
                    "friendly": (
                        "能够降低仁川港入口所受观察和火力威胁，"
                        "保障后续舰艇与登陆艇进入"
                    ),
                    "enemy": (
                        "能够观察并火力作用港口入口和邻近岸滩，"
                        "阻碍登陆力量进入仁川港"
                    ),
                },
                relevance={
                    "mission": "控制月尾岛是建立仁川敌后空间入口的前提",
                    "approach": "月尾岛位于飞鱼航道末端和仁川港入口侧翼",
                },
            ),
            KeyTerrain(
                key_area=Area(name="仁川港岸滩、海堤与港区出口"),
                affected_area=Area(name="仁川港登陆地域及通往金浦的道路入口"),
                control_effects={
                    "friendly": "能够建立并维持由海上转入陆上的登陆入口",
                    "enemy": "能够将登陆力量限制在岸滩或海堤外侧",
                },
                relevance={
                    "mission": "控制港区出口才能使登陆行动继续向内陆发展",
                    "approach": "这里是海上接近路转换为陆上接近路的连接地域",
                },
            ),
            KeyTerrain(
                key_area=Area(name="金浦—首尔交通走廊"),
                affected_area=Area(name="首尔地区主要交通分配体系"),
                control_effects={
                    "friendly": (
                        "能够接近并控制首尔交通枢纽，干扰朝军南北补给、"
                        "增援、机动和撤退联系"
                    ),
                    "enemy": "能够保持仁川与首尔之间的阻隔并维持南北交通联系",
                },
                relevance={
                    "mission": "该走廊把仁川登陆入口与首尔交通体系连接起来",
                    "approach": "它构成登陆力量由仁川向首尔发展的主要陆上通道",
                },
            ),
        ],
        obstacles=[
            Obstacle(
                name="仁川港大潮差、浅滩和泥滩",
                kind="natural",
                obstacle_area=Area(name="仁川港外浅水区及登陆岸滩前沿"),
                movement_effect={
                    "passage": "低潮时登陆艇和舰艇难以接近岸滩",
                    "deployment": "可供登陆、卸载和后续进入的时间受到潮位限制",
                },
                passage_requirements=[
                    "根据潮汐资料确定高潮通行窗口",
                    "在适宜潮位内完成接近、靠岸和越过滩头",
                ],
            ),
            Obstacle(
                name="飞鱼航道狭窄弯曲水道",
                kind="natural",
                obstacle_area=Area(name="飞鱼航道"),
                movement_effect={
                    "passage": "舰艇只能沿有限水道纵向通过，航行调整空间较小",
                    "deployment": "舰艇难以在航道内同时展开，进入次序受到限制",
                },
                passage_requirements=[
                    "确认航道水深、宽度和转向位置",
                    "按照航行次序通过航道",
                ],
            ),
            Obstacle(
                name="仁川港海堤",
                kind="artificial",
                obstacle_area=Area(name="仁川港红滩和蓝滩海堤"),
                movement_effect={
                    "passage": "登陆人员不能从登陆艇直接进入港区",
                    "deployment": "海堤出口限制登陆力量由岸滩向港区展开",
                },
                passage_requirements=[
                    "在适宜潮位接近海堤",
                    "具备越过海堤或打开港区入口的条件",
                ],
            ),
        ],
        cover_and_concealment=[
            CoverAndConcealment(
                cover_area=Area(name="月尾岛高地背坡、岩体及既有工事"),
                concealment_area=Area(name="月尾岛植被和建筑遮挡地域"),
                threats={
                    "fire": "来自舰炮、航空火力和地面直射火力的威胁",
                    "observation": "来自海上、空中和邻近高地的观察威胁",
                },
                effective_conditions={
                    "cover": "人员和装备位于能够阻挡直射火力的地形或工事后方",
                    "concealment": "植被、建筑或岛体能够阻断敌方视线",
                },
                limitations={
                    "cover": "背坡和工事不能完全抵御航空火力及间接火力",
                    "concealment": "接近岸线、道路和制高点后容易重新暴露",
                },
            ),
            CoverAndConcealment(
                cover_area=Area(name="仁川港区坚固建筑及街道两侧"),
                concealment_area=Area(name="仁川港密集建筑和街巷内部"),
                threats={
                    "fire": "来自港区道路、路口和建筑内部的地面火力威胁",
                    "observation": "来自港区高层建筑和道路轴线方向的观察威胁",
                },
                effective_conditions={
                    "cover": "建筑结构保持完整并能阻挡直射火力",
                    "concealment": "建筑和街巷能够切断对方观察视线",
                },
                limitations={
                    "cover": "建筑损毁后可能失去掩蔽作用并阻塞道路",
                    "concealment": "通过开阔路口、岸滩和主要道路时会失去隐蔽",
                },
            ),
        ],
    )

oakoc_res = build_inchon_oakoc_result()


class FormationAction(BaseModel):
    "沿OAKOC路径形成决定性条件的一项状态转换"
    act_name: str = Field(min_length=1,description="本次行动的名称") 
    act_area: Area = Field(description="行动所在地域")
    act_target: list[str] = Field(min_length=1,description="行动的作用目标") 
    act_mechanism: list[str] = Field(min_length=1,description="行动应该如何达到预期的状态")  
    expected_state: list[str] = Field(min_length=1,description="行动预期达到的状态")  
    indicators: list[str] = Field(min_length=1,description="达到该状态的判断依据")

class CandidateDirection(BaseModel):
    "由OAKOC生成结果和决定性条件共同形成的候选作战方向"
    path: OAKOCResult  # OAKOC的完整生成结果
    decisive_condition: DecisiveCondition  # 决定性条件
    formation_actions: list[FormationAction] = Field(
        min_length=1, description="根据OAKOC生成结果，达到决定性条件所依次采取的行动信息"
    ) 

def propose_avenue_of_approach(
    decisive_condition: DecisiveCondition,
    oakoc_result: OAKOCResult,
    formation_actions: list[FormationAction],
) -> CandidateDirection:
    return CandidateDirection(
        path=oakoc_result,
        formation_actions=formation_actions,
        decisive_condition=decisive_condition,
    )

candidate_direction = propose_avenue_of_approach(
    decisive_res, oakoc_res,
    formation_actions=[
        FormationAction(
        act_name="沿飞鱼航道进入",
        act_area=Area(name="飞鱼航道"),
        act_target=[
            "飞鱼航道通行水域",
            "月尾岛近岸行动位置",
        ],
        act_mechanism=[
            "利用OAKOC分析确认的高潮通行窗口进入飞鱼航道",
            "按照航道通行次序通过狭窄水道",
            "到达月尾岛近岸行动位置",
        ],
        expected_state=[
                "突击力量已经通过飞鱼航道并到达月尾岛近岸行动位置",
        ],
        indicators=[
                "行动编组报告已经完成飞鱼航道通行",
                "位置报告与月尾岛近岸预定位置相符",
        ],

        ),
        FormationAction(
        act_name="控制月尾岛",
        act_area=Area(name="月尾岛"),
        act_target=[
            "月尾岛主要防御位置",
            "敌方对仁川港入口的观察和火力控制能力",
        ],
        act_mechanism=[
            "控制月尾岛主要防御位置",
            "使敌方失去对月尾岛主要地域的控制",
            "消除来自月尾岛方向对仁川港入口的有效火力阻断",
        ],
        expected_state=[
                "月尾岛主要地域由我方控制",
                "敌方不能继续利用月尾岛有效阻断仁川港入口",
        ],
        indicators=[
                "月尾岛主要防御位置停止有组织抵抗",
                "我方能够控制月尾岛主要地域",
                "来自月尾岛的火力不能继续有效阻断仁川港入口",
        ],
        ),
        FormationAction(
        act_name="夺控登陆岸滩与海堤出口",
        act_area=Area(name="仁川港红滩和蓝滩"),
        act_target=[
            "仁川港登陆岸滩",
            "海堤及其通往港区的出口",
        ],
        act_mechanism=[
            "利用OAKOC分析确认的主登陆潮汐窗口接近岸滩",
            "控制红滩和蓝滩登陆地域",
            "打开由海堤进入港区的通道",
        ],
        expected_state=[
                "仁川港岸上登陆入口已经建立",
                "登陆力量能够由岸滩向港区展开",
        ],
        indicators= [
                "红滩和蓝滩已经形成可使用的登陆地域",
                "海堤出口已经被控制或打开",
                "后续力量能够由岸滩进入港区",
        ],
        ),
        FormationAction(
        act_name="控制港区并打通内陆出口",
        act_area=Area(name="仁川港港区"),
        act_target=[
            "仁川港主要地域",
            "港区通往金浦方向的道路出口",
        ],
        act_mechanism=[
            "控制港区主要地域及道路出口",
            "连接登陆地域与仁川至金浦交通通道",
            "保持后续力量由港区向内陆进入的连续性",
        ],
        expected_state=[
                "仁川港区及主要道路出口由我方控制",
                "登陆力量能够继续向金浦和首尔方向发展",
            ],
        indicators= [
                "港区主要地域不再由敌方有效控制",
                "仁川至金浦方向的主要道路能够通行",
                "后续力量能够由登陆地域转入内陆交通走廊",
        ],
        ),
        FormationAction(
        act_name="控制或阻断首尔交通体系",
        act_area=Area(name="首尔地区主要交通枢纽及南北交通通道"),
        act_target=[
            "首尔地区主要交通分配体系",
            "朝军南部集团与北方后方之间的主要交通联系",
        ],
        act_mechanism=[
            "控制首尔地区关键交通枢纽和主要通道",
            "阻断朝军向南部集团实施补给和增援的交通联系",
            "限制朝军南部集团的机动和撤退能力",
        ],
        expected_state=[
                "首尔地区主要交通分配体系已被控制或受到有效阻断",
                "朝军南部集团与北方后方之间的补给、增援、机动和撤退联系"
                "被实质切断或严重扰乱",
                "朝军难以继续维持釜山正面的攻势",
        ],
        indicators= [
                "首尔地区关键交通枢纽受到控制或有效阻断",
                "朝军南北主要交通联系无法正常维持",
                "朝军南部集团补给和增援能力明显下降",
                "朝军南部集团停止攻势或开始后撤",
        ],
    ),
]
)

print(candidate_direction)

