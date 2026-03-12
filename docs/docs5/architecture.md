# linkmic_understand_svr 项目文档

## 1. 项目目的

`linkmic_understand_svr` 是一个基于 Kitex 框架的 RPC 服务，主要用于 **连麦直播内容理解和分类标注**。

### 核心定位

1. **多房间直播内容分类**: 对多嘉宾连麦直播间进行玩法分类（如 Dating、BoxBattle、Consulting、Debating、TalentShow 等）
2. **BPO 审核回调处理**: 接收 TCS（内容审核平台）的审核结果回调，处理人工标注数据
3. **模型管理**: 支持 LLM 分类模型的更新和指标监控
4. **数据采集与管理**: 从 RTC 获取直播切片数据，存储到对象存储

---

## 2. 代码链路

### 2.1 项目结构

```
linkmic_understand_svr/
├── main.go                 # 入口文件，启动 Kitex Server
├── handler.go              # RPC 接口实现入口
├── handlers/               # 各接口的 Handler 实现
│   ├── operate_file.go           # 文件操作（获取音频切片）
│   ├── check_new_model.go        # 检查新模型并推送指标
│   ├── check_selection.go        # 检查房间筛选
│   ├── get_all_selected_room.go  # 获取所有选中房间
│   ├── get_gameplay_tag.go       # 获取房间玩法标签
│   ├── tcs_task_result.go        # TCS 审核结果回调处理
│   ├── notify_model_update.go    # 模型更新通知
│   └── update_model_service_callback.go  # 模型更新回调
├── services/               # 业务服务层
│   ├── room.go             # 房间 SDK 调用
│   ├── rtc.go              # RTC 切片获取
│   ├── tos.go              # TOS 对象存储操作
│   ├── hdfs.go             # HDFS 文件操作
│   ├── lark.go             # 飞书消息推送
│   ├── eventbus.go         # EventBus 消息发送
│   ├── arch.go             # 模型服务更新
│   └── mg_room_fragment_material.go  # 数据库操作
├── model/                  # 数据模型
├── constdef/               # 常量定义
├── tcc/                    # 配置中心
├── utils/                  # 工具函数
└── kitex_gen/              # Kitex 生成的代码
```

### 2.2 启动流程

```
main.go
  ├── linkmicunderstandservice.NewServer()  # 创建 Kitex Server
  ├── Init()
  │     ├── services.InitTos()              # 初始化 TOS 客户端
  │     └── handlers.InitCacheRefresher()   # 初始化房间缓存刷新器
  └── svr.Run()                             # 启动服务
```

---

## 3. 主要方法

### 3.1 RPC 接口列表

| 接口名 | 功能描述 |
|--------|----------|
| `OperateFile` | 获取房间指定时间段的音频切片 |
| `GetLeaveCategorySurvey` | 获取离场分类问卷 |
| `SubmitLeaveCategorySurvey` | 提交离场分类问卷 |
| `MsetTaskResult_` | TCS 审核结果回调处理 |
| `CheckNewModel` | 检查 HDFS 上是否有新模型 |
| `NotifyModelUpdate` | 通知模型更新 |
| `UpdateModelServiceCallback` | 模型更新结果回调 |
| `GetGameplayTag` | 获取房间/主播的玩法标签 |
| `CheckSelection` | 检查房间是否被选中 |
| `GetAllSelectedRoom` | 获取所有选中的房间列表 |

### 3.2 核心方法详解

#### 3.2.1 OperateFile - 获取音频切片

**位置**: `handlers/operate_file.go`

**功能**: 根据房间ID和时间范围，从 RTC 获取直播音频切片，存储到 TOS

**流程**:
1. 参数校验（roomId, startTime, endTime）
2. 调用 `GetRtcSlice` 获取 RTC 切片数据
3. 遍历音频单元，下载音频文件
4. 上传到自有 TOS，并跨区域复制

#### 3.2.2 MsetTaskResult_ - TCS 审核回调

**位置**: `handlers/tcs_task_result.go`

**功能**: 处理 TCS 平台的审核结果回调

**流程**:
1. 根据 ProjectId 区分处理类型：
   - `GoldenCaseReviewQueueID`: 专家审核回调 → 发送 EventBus 事件
   - 其他: BPO 审核回调 → 更新数据库
2. 解析审核表单，提取分类标签
3. 多人审核时采用投票机制确定最终结果
4. 更新 `multi_guest_room_fragment_material` 表

#### 3.2.3 CheckNewModel - 检查新模型

**位置**: `handlers/check_new_model.go`

**功能**: 检查 HDFS 上是否有新的模型发布，推送指标到飞书

**流程**:
1. 检查最近 7 天的 HDFS 目录
2. 读取 `metrics.json` 文件
3. 格式化准确率、召回率指标
4. 生成混淆矩阵并上传飞书表格
5. 推送消息到飞书群

#### 3.2.4 GetAllSelectedRoom - 获取选中房间

**位置**: `handlers/get_all_selected_room.go`

**功能**: 获取当前需要进行内容理解的所有连麦房间

**流程**:
1. 从缓存获取房间列表（10分钟刷新）
2. 调用 `room.GetAllOnlineRoomsData` 获取所有在线房间
3. 根据 AB 参数和国家配置筛选房间
4. 过滤出多嘉宾模式房间

---

## 4. 实现方式

### 4.1 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| RPC 框架 | Kitex | 服务间通信 |
| 对象存储 | TOS | 存储音频、图片文件 |
| 消息队列 | EventBus | 异步事件通知 |
| 配置中心 | TCC | 动态配置管理 |
| 文件系统 | HDFS | 模型文件存储 |
| 数据库 | MySQL (GORM) | 标注数据存储 |
| 通知 | 飞书 API | 消息推送 |

### 4.2 设计模式

#### Handler 模式
每个 RPC 接口对应一个 Handler 结构体，统一处理流程：

```go
type XXXHandler struct {
    ctx context.Context
    req *XXXRequest
}

func NewPreXXXHandler(ctx, req) *XXXHandler {
    return &XXXHandler{ctx, req}
}

func (h *XXXHandler) Handle() (resp, err) {
    // 业务逻辑
}
```

#### 异步处理
耗时操作使用 goroutine 异步执行：

```go
utils.Go(ctx, func() {
    // 异步逻辑，如检查模型、发送消息等
})
```

#### 缓存策略
使用 `anycache` 实现房间列表缓存：
- TTL: 10 分钟
- 异步刷新: 每 10 秒
- 过期策略: 使用过期数据异步刷新

### 4.3 玩法分类体系

**一级分类**:
- `BoxBattle` - 对战
- `Consulting` - 咨询
- `Dating` - 约会（含二级 TMO）
- `Debating` - 辩论
- `TalentShow` - 才艺
- `NoGameplay` - 无玩法
- `UnCovered` - 未覆盖

**内容分类**:
- Music, Dance, Arts, Sports&Health, Food, Game
- Society&Culture, Relationship, Film&TV&ACG
- Knowledge, Education, Mysticism, RandomChatting
- Event&Party, ProductSales, EngagementBait, Others

---

## 5. 数据流向

### 5.1 整体数据流图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部系统                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │   RTC   │  │   TCS   │  │  Room   │  │  HDFS   │  │  Lark   │           │
│  │ (切片)  │  │ (审核)  │  │  SDK    │  │ (模型)  │  │ (飞书)  │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
│       │            │            │            │            │                 │
└───────┼────────────┼────────────┼────────────┼────────────┼─────────────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        linkmic_understand_svr                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         handler.go (RPC 入口)                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│        ┌───────────────────────────┼───────────────────────────┐            │
│        ▼                           ▼                           ▼            │
│  ┌───────────┐              ┌───────────┐              ┌───────────┐        │
│  │OperateFile│              │TcsTask    │              │CheckNew   │        │
│  │  Handler  │              │Result     │              │  Model    │        │
│  └─────┬─────┘              └─────┬─────┘              └─────┬─────┘        │
│        │                          │                          │              │
│        ▼                          ▼                          ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                            services/                                  │   │
│  ├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤   │
│  │   rtc.go    │   tos.go    │  eventbus.go│   hdfs.go   │   lark.go   │   │
│  │  (切片获取) │ (对象存储)  │ (消息队列)  │ (文件读取)  │ (消息推送)  │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│     TOS     │      │  EventBus   │      │    MySQL    │
│  (音频存储) │      │ (异步事件)  │      │ (标注数据)  │
└─────────────┘      └─────────────┘      └─────────────┘
```

### 5.2 TCS 审核回调数据流

```
TCS 平台
    │
    │ MSetTaskResultReq (审核结果)
    ▼
┌───────────────────────────────────┐
│      TcsTaskResultHandler         │
│    (handlers/tcs_task_result.go)  │
├───────────────────────────────────┤
│ 1. 解析审核表单                    │
│ 2. 提取玩法分类和内容分类           │
│ 3. 多人投票确定最终结果            │
└───────────────────────────────────┘
    │
    ├─────────────────────┐
    │                     │
    ▼                     ▼
┌───────────┐      ┌───────────┐
│  更新DB   │      │ EventBus  │
│ (BPO审核) │      │(GoldenCase)│
└───────────┘      └───────────┘
    │                     │
    ▼                     ▼
┌───────────┐      ┌─────────────────┐
│  MySQL    │      │ linkmic_llm_    │
│ (标注数据) │      │ understanding   │
└───────────┘      │ (消费事件)       │
                   └─────────────────┘
```

### 5.3 模型检查与更新流程

```
定时触发/手动调用
        │
        ▼
┌───────────────────────────────────┐
│      CheckNewModelHandler         │
├───────────────────────────────────┤
│ 1. 检查 HDFS 最近7天目录          │
│ 2. 验证 metrics.json 存在         │
│ 3. 读取并解析指标数据              │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│         格式化指标                 │
├───────────────────────────────────┤
│ • 整体准确率                       │
│ • VIP 准确率                       │
│ • 各分类准召                       │
│ • 混淆矩阵                        │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│      推送飞书消息                  │
│  • 模型路径                        │
│  • 准确率指标                      │
│  • 混淆矩阵表格链接                │
└───────────────────────────────────┘
```

---

## 6. 配置说明

### TCC 配置项

| 配置 Key | 用途 |
|----------|------|
| `TnsTos` | TNS TOS 存储配置（音频源） |
| `SelfTos` | 自有 TOS 存储配置 |
| `Svr` | 服务配置（飞书群ID等） |
| `RoomSelection` | 房间筛选配置（国家、分流） |
| `GoldenSet` | Golden Set 配置（Prompt Key、TCS场景等） |

### 环境要求

- 仅在 `VREGION_SINGAPORECENTRAL` 和 `VREGION_USEAST` 启用完整功能
- HDFS 客户端需要 `harunava` 集群访问权限

---

## 7. 依赖服务

| 服务 | PSM | 用途 |
|------|-----|------|
| tikcast_rag_server | tikcast.rag.server | RTC 切片获取 |
| tikcast_llm_model_guardian | tikcast.llm.model.guardian | 模型服务管理 |
| room_sdk | - | 房间数据获取 |
| EventBus | - | 异步消息发送 |
| TOS | - | 对象存储 |
| HDFS | harunava | 模型文件存储 |
| 飞书 | - | 消息通知 |
