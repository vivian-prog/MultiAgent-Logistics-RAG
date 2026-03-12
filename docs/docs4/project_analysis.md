# linkmic_understand_api 项目分析

## 1. 项目目的

`linkmic_understand_api` 是一个 **HTTP API 网关服务**，为直播内容理解系统提供 Web 接口。主要功能包括：

- **Web前端API**：提供直播片段数据查询、分类标注、数据集管理等接口
- **飞书机器人集成**：通过飞书 Bot 进行内容理解任务触发和模型管理
- **内部服务API**：提供数据生成、ASR对比、分类聚合等内部功能
- **Pipeline监控**：提供模型监控、规则生产、任务创建等运维接口
- **数据标注平台**：支持人工标注分类、评论管理等标注工作

---

## 2. 代码链路

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              入口层 (main.go)                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Hertz HTTP Server                                                              │
│  ├── initializer() - 初始化 TCC配置、日志、Redis、VikingDB、SSO                  │
│  ├── CORS 中间件                                                                │
│  └── register(r) + customizeRegister(r) - 注册路由                              │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           路由层 (router.go)                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  /api/linkmic_  │  │  /api/linkmic_  │  │  /api/linkmic_  │                  │
│  │ understand_bot  │  │ understand_web  │  │ understand_in   │                  │
│  │   (飞书机器人)    │  │   (Web前端)     │  │   (内部接口)     │                  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                  │
│           │                    │                    │                            │
│  ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐                  │
│  │  /api/linkmic_  │  │  /api/linkmic_  │  │  /api/linkmic_  │                  │
│  │understand_      │  │understand_      │  │understand_      │                  │
│  │   pipeline      │  │   fest          │  │   survey        │                  │
│  │   (运维管道)      │  │   (节日活动)     │  │   (问卷调查)     │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                  │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Handler层 (handler/)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  handler/web/                    handler/in/                    handler/bot/    │
│  ├── generate_understand.go      ├── generate_summary.go        ├── message.go  │
│  ├── get_fragment.go             ├── update_fragment.go         ├── test.go     │
│  ├── modify_category.go          ├── get_asr_compare.go         └── evaluation.go
│  ├── get_dataset.go              ├── room_all_fragment.go                       │
│  ├── get_evaluation_metrics.go   ├── anchor_category_agg.go                    │
│  └── get_similar_sample.go       └── arch_asr.go                               │
│                                                                                  │
│  handler/pipeline/               handler/fest/                  handler/survey/ │
│  ├── check_new_model.go          ├── generate.go                └── generate.go │
│  ├── monitor_matrix.go           └── sheet.go                                   │
│  ├── create_tcs_task.go                                                         │
│  └── rule_prod.go                                                               │
│                                                                                  │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Service层 (services/)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  数据访问服务:                                                                    │
│  ├── mg_room_fragment_material.go    - 直播片段素材数据访问                       │
│  ├── mg_room_category_agg.go         - 房间分类聚合                              │
│  ├── mg_anchor_category_agg.go       - 主播分类聚合                              │
│  ├── mg_fragment_evaluation_metrics  - 评估指标                                  │
│  └── mysql.go                        - 数据库连接管理                             │
│                                                                                  │
│  外部服务调用:                                                                    │
│  ├── eventbus.go                     - EventBus消息生产者                        │
│  ├── svr.go                          - understand_svr RPC调用                    │
│  ├── arch.go                         - ARCH服务调用                              │
│  ├── arch_asr.go                     - ARCH ASR服务                              │
│  ├── arch_embedding.go               - ARCH Embedding服务                        │
│  ├── tns.go                          - TNS服务                                   │
│  ├── tos.go                          - TOS对象存储                               │
│  └── vikingdb.go                     - VikingDB向量数据库                        │
│                                                                                  │
│  其他服务:                                                                        │
│  ├── redis.go                        - Redis缓存                                 │
│  ├── es.go                           - Elasticsearch                             │
│  ├── host.go                         - 主播标签管理                              │
│  └── metrics.go                      - 监控指标                                  │
│                                                                                  │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          LLM服务层 (llmservices/)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  api.go              - LLM调用封装 (重试、限流处理)                               │
│  gptv.go             - GPT-V 多模态调用                                          │
│  gpt4turbov.go       - GPT-4 Turbo Vision 调用                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          评估层 (evaluation/)                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  category_prompt.go     - 分类Prompt                                            │
│  quality_prompt.go      - 质量Prompt                                            │
│  topic_prompt.go        - 话题Prompt                                            │
│  atmosphere_prompt.go   - 氛围Prompt                                            │
│  opinion_prompt.go      - 观点Prompt                                            │
│  merge_prompt.go        - 合并Prompt                                            │
│  comm.go                - 公共方法                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 主要方法

### 3.1 Web API 主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `handler/web/generate_understand.go:25` | `HandleGenerateUnderstandAPI` | 触发直播间内容理解任务 |
| `handler/web/get_fragment.go:23` | `HandleGetFragmentAPI` | 获取单个直播片段详情 |
| `handler/web/get_fragment_batch.go` | `HandleGetFragmentBatchAPI` | 批量获取直播片段 |
| `handler/web/modify_category.go:21` | `HandleModifyCategoryAPI` | 修改直播片段分类标注 |
| `handler/web/modify_category_batch.go` | `HandleModifyCategoryBatchAPI` | 批量修改分类标注 |
| `handler/web/get_dataset.go` | `HandleGetDatasetAPI` | 获取数据集列表 |
| `handler/web/get_evaluation_metrics.go` | `HandleGetEvaluationMetricsAPI` | 获取评估指标 |
| `handler/web/get_similar_sample.go` | `HandleGetSimilarSampleAPI` | 获取相似样本(RAG) |
| `handler/web/create_prompt_version.go` | `HandleCreatePromptVersionAPI` | 创建Prompt版本 |
| `handler/web/timer_collect_dataset.go` | `HandleTimerCollectDatasetAPI` | 定时收集数据集 |

### 3.2 Bot API 主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `handler/bot/message.go:34` | `HandleBotMessage` | 处理飞书机器人消息 |
| `handler/bot/message.go:145` | `cmdHelp` | 显示帮助信息 |
| `handler/bot/message.go:192` | `cmdGoldenSet` | Golden Set操作命令 |
| `handler/bot/evaluation.go` | `EvaluationAPI` | 评估API |

### 3.3 Internal API 主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `handler/in/generate_summary.go:19` | `GenerateSummaryAPI` | 生成摘要任务 |
| `handler/in/update_fragment.go` | `UpdateFragmentAPI` | 更新片段数据 |
| `handler/in/room_all_fragment.go` | `RoomAllFragmentAPI` | 获取房间所有片段 |
| `handler/in/anchor_category_agg.go` | `AnchorCategoryAggAPI` | 主播分类聚合 |
| `handler/in/get_asr_compare.go` | `GetAsrCompareAPI` | ASR对比分析 |

### 3.4 Pipeline API 主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `handler/pipeline/check_new_model.go` | `CheckNewModelAPI` | 检查新模型 |
| `handler/pipeline/monitor_matrix.go` | `MonitorMatrixAPI` | 监控矩阵 |
| `handler/pipeline/create_tcs_task.go` | `CreateTcsTaskAPI` | 创建TCS任务 |
| `handler/pipeline/rule_prod.go` | `RuleProdAPI` | 规则生产 |

### 3.5 Service 层主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `services/mg_room_fragment_material.go:217` | `GetMultiGuestRoomFragmentMaterialByRoomIDAndType` | 按房间ID和类型查询片段素材 |
| `services/mg_room_fragment_material.go:581` | `UpdateMultiGuestRoomFragmentMaterialById` | 更新片段素材 |
| `services/eventbus.go:112` | `SendGenerateSummaryMsg` | 发送生成摘要消息到EventBus |
| `services/eventbus.go:135` | `SendUpdateFragmentMsg` | 发送更新片段消息 |
| `services/svr.go:15` | `OperateFile` | 调用understand_svr操作文件 |
| `services/svr.go:36` | `NotifyModelUpdate` | 通知模型更新 |

---

## 4. 实现方式

### 4.1 架构模式

- **HTTP API 网关**：基于 Hertz 框架，提供 RESTful API
- **分层架构**：Handler → Service → LLM/External Service
- **消息驱动**：通过 EventBus 与下游服务异步通信
- **RPC调用**：通过 Kitex 调用 understand_svr 后端服务

### 4.2 数据流

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              请求入站                                            │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                            │
│  │ Web前端    │    │ 飞书Bot    │    │ 内部服务   │                            │
│  │ (用户操作)  │    │ (命令触发)  │    │ (定时任务)  │                            │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘                            │
│        │                 │                 │                                     │
│        └─────────────────┼─────────────────┘                                     │
│                          ▼                                                       │
│                    ┌──────────┐                                                  │
│                    │  Hertz   │                                                  │
│                    │  Server  │                                                  │
│                    └────┬─────┘                                                  │
└─────────────────────────┼───────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Handler处理                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  1. 参数解析与校验                                                         │  │
│  │  2. 鉴权验证 (bdsso.SessionMiddleware)                                     │  │
│  │  3. 业务逻辑调用                                                           │  │
│  │  4. 响应封装                                                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   MySQL DB   │  │   EventBus   │  │  RPC Service │
│  (数据存储)   │  │ (消息队列)    │  │ (后端服务)    │
└──────────────┘  └──────────────┘  └──────────────┘
        │               │               │
        │               │               │
        ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           下游处理                                               │
│                                                                                  │
│  MySQL:                                                                          │
│  ├── multi_guest_admin.multi_guest_room_fragment_material (片段素材表)          │
│  ├── multi_guest_admin.multi_guest_room_fragment_manual_annotation_log (标注日志)│
│  └── live_link_mic.* (直播间相关表)                                              │
│                                                                                  │
│  EventBus Topics:                                                                │
│  ├── tiktok.live.multi_guest.generate_summary (生成摘要)                        │
│  ├── tiktok.live.multi_guest.update_fragment (更新片段)                         │
│  ├── tiktok.webcast.linkmic.llm.room_category_agg (房间分类聚合)                 │
│  └── tiktok.webcast.linkmic.llm.anchor_category_agg (主播分类聚合)               │
│                                                                                  │
│  RPC (understand_svr):                                                           │
│  ├── OperateFile - 文件操作                                                      │
│  ├── NotifyModelUpdate - 模型更新通知                                            │
│  └── CheckNewModel - 检查新模型                                                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 关键技术

| 技术 | 用途 |
|------|------|
| Hertz | HTTP服务框架 |
| Kitex | RPC客户端 |
| EventBus | 消息队列 |
| MySQL (GORM) | 关系数据库 |
| Redis | 缓存 |
| Elasticsearch | 搜索引擎 |
| VikingDB | 向量数据库 (RAG) |
| TOS | 对象存储 |
| 飞书 Open API | Bot集成 |
| GPT-4o/GPT-V | LLM模型调用 |

### 4.4 分类体系

项目支持以下直播内容分类：

```
一级分类:
├── BoxBattle      (盲盒对战)
├── TalentShow     (才艺展示)
│   └── Music, DJ, Dance, Art, OtherTalents
├── Consulting     (咨询)
│   └── Relationship, Law, MetaphysicalConsultation, Health...
├── Dating         (约会)
├── Debating       (辩论)
│   └── Relationship, SexualOrientation, Politics&Society...
├── NoGameplay     (非玩法)
├── UnCovered      (未覆盖)
└── Abandon        (废弃)
```

### 4.5 EventBus 消息生产

服务通过 EventBus 向下游发送多种消息：

| Topic | 用途 |
|-------|------|
| `tiktok.live.multi_guest.generate_summary` | 触发生成摘要任务 |
| `tiktok.live.multi_guest.update_fragment` | 更新片段数据 |
| `tiktok.webcast.linkmic.llm.room_category_agg` | 房间分类聚合 |
| `tiktok.webcast.linkmic.llm.anchor_category_agg` | 主播分类聚合 |
| `tiktok.webcast.linkmic.llm.annotated_dataset` | 标注数据集同步 |
| `tiktok.live.multi_guest.update_golden_set` | Golden Set更新 |

---

## 5. 代码逻辑图

### 5.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              外部客户端                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Web前端  │  │ 飞书Bot  │  │ 内部服务 │  │ 定时任务 │  │ 监控系统 │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
└───────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┘
        │             │             │             │             │
        └─────────────┴─────────────┼─────────────┴─────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         linkmic_understand_api                                  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                          Hertz HTTP Server                                 │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   /bot/*    │ │   /web/*    │ │   /in/*     │ │ /pipeline/* │          │ │
│  │  │ 飞书机器人   │ │ Web前端API  │ │ 内部接口    │ │ 运维管道    │          │ │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘          │ │
│  └─────────┼───────────────┼───────────────┼───────────────┼──────────────────┘ │
│            │               │               │               │                    │
│            └───────────────┴───────┬───────┴───────────────┘                    │
│                                      │                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                            Handler Layer                                   │ │
│  │  • 参数校验  • 鉴权验证  • 业务编排  • 响应封装                              │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                            Service Layer                                   │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐  │ │
│  │  │   MySQL DB    │ │   EventBus    │ │  RPC Client   │ │    Redis      │  │ │
│  │  │   (GORM)      │ │  (Producer)   │ │(understand_svr)│ │   (Cache)    │  │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                          LLM Services Layer                                │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                    │ │
│  │  │    GPT-4o     │ │    GPT-V      │ │   Embedding   │                    │ │
│  │  │  (文本生成)    │ │  (多模态)     │ │  (向量化)     │                    │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘                    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    MySQL      │ │   EventBus    │ │understand_svr │ │  VikingDB     │
│ multi_guest_  │ │   Topics      │ │   (RPC服务)   │ │  (向量数据库) │
│    admin      │ │               │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

### 5.2 飞书Bot消息处理流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  飞书用户   │────▶│  飞书服务   │────▶│  Bot API    │────▶│ HandleBot   │
│  发送消息   │     │  (回调)     │     │  /message   │     │  Message()  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                    ┌──────────────────────────────────────────────┤
                    │                                              │
                    ▼                                              ▼
            ┌──────────────┐                              ┌──────────────┐
            │ 命令解析     │                              │ JSON解析     │
            │ (/help等)    │                              │              │
            └──────┬───────┘                              └──────┬───────┘
                   │                                             │
        ┌──────────┴──────────┐                    ┌────────────┴────────────┐
        │                     │                    │                         │
        ▼                     ▼                    ▼                         ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐          ┌──────────────┐
│   /help      │    │/golden_set   │    │ type=        │          │ type=        │
│   帮助信息    │    │ Golden Set   │    │ "understand" │          │"update_model"│
│              │    │   操作       │    │              │          │              │
└──────────────┘    └──────────────┘    └──────┬───────┘          └──────┬───────┘
                                               │                         │
                                               ▼                         ▼
                                    ┌──────────────┐           ┌──────────────┐
                                    │ EventBus发送 │           │ RPC调用      │
                                    │GenerateSummary│           │NotifyModel   │
                                    │   消息       │           │  Update      │
                                    └──────────────┘           └──────────────┘
```

### 5.3 内容理解请求流程

```
┌─────────────┐     ┌─────────────────────────────────────────────────────────┐
│ Web前端请求 │────▶│ POST /api/linkmic_understand_web/generate_understand   │
└─────────────┘     └──────────────────────────────┬──────────────────────────┘
                                                   │
                                                   ▼
                    ┌──────────────────────────────────────────────────────────┐
                    │              HandleGenerateUnderstandAPI                  │
                    │  1. 参数校验 (roomID, indicatorType)                       │
                    │  2. IDC判断 - 非MALIVA转发到FaaS                          │
                    │  3. 构造 GenerateSummaryMsg                               │
                    │  4. EventBus 发送消息                                     │
                    └──────────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                    ┌──────────────────────────────────────────────────────────┐
                    │                   EventBus Topic                         │
                    │        tiktok.live.multi_guest.generate_summary          │
                    └──────────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                    ┌──────────────────────────────────────────────────────────┐
                    │              下游消费者 (linkmic_llm_data_grab)            │
                    │  • 拉取直播数据 (视频、音频、评论)                          │
                    │  • 调用 ASR 服务                                          │
                    │  • 发送到 understand_svr 进行 LLM 理解                    │
                    └──────────────────────────────────────────────────────────┘
```

---

## 6. 数据流动

### 6.1 数据写入流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              数据写入流程                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1. 人工标注流程:                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ Web前端  │───▶│ /modify_ │───▶│ Handler  │───▶│ MySQL    │                  │
│  │ 标注分类 │    │ category │    │ 鉴权+更新 │    │ DB更新   │                  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘                  │
│                                        │                                        │
│                                        ▼                                        │
│                                 ┌──────────┐                                    │
│                                 │ 标注日志 │                                    │
│                                 │ 表写入   │                                    │
│                                 └──────────┘                                    │
│                                                                                  │
│  2. 自动理解流程:                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ 触发请求 │───▶│ EventBus │───▶│ data_grab│───▶│understand│                  │
│  │(Bot/API)│    │  发送    │    │ 数据准备 │    │ _svr处理 │                  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘                  │
│                                                          │                      │
│                                                          ▼                      │
│                                                   ┌──────────┐                  │
│                                                   │ MySQL写入│                  │
│                                                   │ 素材+结果│                  │
│                                                   └──────────┘                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 数据读取流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              数据读取流程                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐                                                                    │
│  │ 请求入站 │                                                                    │
│  └────┬─────┘                                                                    │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                           Handler 处理                                    │  │
│  │  • 参数解析                                                               │  │
│  │  • 条件构建 (roomID, anchorID, category, timeRange等)                     │  │
│  │  • 分页处理 (offset, limit)                                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         Service 层查询                                    │  │
│  │                                                                           │  │
│  │  GetMultiGuestRoomFragmentMaterialsByTime(                               │  │
│  │      id, roomID, anchorID, offset, limit,                                │  │
│  │      llmCategory, manualCategory, strategyCategory, tcsCategory,         │  │
│  │      dataset, strategyTrouble, startTime, endTime                        │  │
│  │  )                                                                        │  │
│  │                                                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                           MySQL 查询                                      │  │
│  │                                                                           │  │
│  │  SELECT * FROM multi_guest_room_fragment_material                        │  │
│  │  WHERE room_id = ? AND indicator_type = ?                                │  │
│  │    AND llm_category = ? AND manual_category = ?                          │  │
│  │    AND indicator_time BETWEEN ? AND ?                                    │  │
│  │  ORDER BY indicator_time DESC                                            │  │
│  │  LIMIT ? OFFSET ?                                                        │  │
│  │                                                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                           数据转换                                        │  │
│  │  • JSON字段解析 (Mp4Uris, Comments, WhisperTexts等)                       │  │
│  │  • URL拼接 (TOS地址)                                                      │  │
│  │  • API响应结构组装                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                           HTTP 响应                                       │  │
│  │  {                                                                        │  │
│  │    "base_resp": {...},                                                    │  │
│  │    "fragment_info_wrapper": {                                             │  │
│  │      "basic_info": {...},                                                 │  │
│  │      "media_info": {...},                                                 │  │
│  │      "llm_info": {...},                                                   │  │
│  │      "manual_info": {...}                                                 │  │
│  │    }                                                                      │  │
│  │  }                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 RAG相似样本检索流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          RAG相似样本检索流程                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ 请求输入 │───▶│ 文本Embed │───▶│ VikingDB │───▶│ 返回相似 │                  │
│  │ (片段ID) │    │  ding生成 │    │ 向量检索 │    │ 样本列表 │                  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘                  │
│                        │                                                         │
│                        ▼                                                         │
│              ┌──────────────────┐                                                │
│              │ Embedding服务    │                                                │
│              │ (title+sticker,  │                                                │
│              │  ASR, Image)     │                                                │
│              └──────────────────┘                                                │
│                                                                                  │
│  数据来源:                                                                       │
│  • TitleStickerEmbedding - 标题贴纸向量                                          │
│  • AsrEmbedding - ASR文本向量                                                    │
│  • ImageEmbedding - 图片向量                                                     │
│                                                                                  │
│  用途: Few-Shot学习样本召回                                                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 目录结构说明

```
linkmic_understand_api/
├── main.go                 # 入口文件，Hertz服务初始化
├── handler.go              # Kitex RPC Handler (未使用)
├── router.go               # 自定义路由注册
├── router_gen.go           # 自动生成的路由
├── build.sh                # 构建脚本
│
├── handler/                # HTTP处理器
│   ├── bot/                # 飞书机器人Handler
│   │   ├── message.go          # 消息处理
│   │   ├── test.go             # 测试API
│   │   └── evaluation.go       # 评估API
│   ├── web/                # Web前端Handler
│   │   ├── generate_understand.go  # 触发理解
│   │   ├── get_fragment.go         # 获取片段
│   │   ├── modify_category.go      # 修改分类
│   │   ├── get_dataset.go          # 获取数据集
│   │   └── get_similar_sample.go   # 相似样本
│   ├── in/                 # 内部接口Handler
│   │   ├── generate_summary.go     # 生成摘要
│   │   ├── update_fragment.go      # 更新片段
│   │   └── anchor_category_agg.go  # 分类聚合
│   ├── pipeline/           # 运维管道Handler
│   ├── fest/               # 节日活动Handler
│   ├── survey/             # 问卷调查Handler
│   └── comm/               # 公共Handler方法
│
├── services/               # 业务服务层
│   ├── mysql.go                # MySQL连接管理
│   ├── mg_room_fragment_material.go  # 片段素材数据访问
│   ├── mg_room_category_agg.go     # 房间分类聚合
│   ├── mg_anchor_category_agg.go   # 主播分类聚合
│   ├── eventbus.go              # EventBus生产者
│   ├── svr.go                   # understand_svr RPC调用
│   ├── arch.go                  # ARCH服务
│   ├── arch_embedding.go        # Embedding服务
│   ├── vikingdb.go              # VikingDB向量库
│   └── redis.go                 # Redis缓存
│
├── llmservices/            # LLM调用服务
│   ├── api.go                  # LLM调用封装
│   ├── gptv.go                 # GPT-V多模态
│   └── gpt4turbov.go           # GPT-4 Turbo Vision
│
├── evaluation/             # 评估Prompt
│   ├── category_prompt.go      # 分类Prompt
│   ├── quality_prompt.go       # 质量Prompt
│   └── topic_prompt.go         # 话题Prompt
│
├── model/                  # 业务模型
├── constdef/               # 常量定义
│   ├── eventbus.go             # EventBus Topic常量
│   ├── comm.go                 # 公共常量(分类、类型)
│   └── errors.go               # 错误定义
│
├── tcc/                    # 动态配置
├── utils/                  # 工具函数
├── tools/                  # 工具脚本
├── sql/                    # SQL脚本
├── conf/                   # 配置文件
├── script/                 # 部署脚本
└── kitex_gen/              # Kitex生成代码
```

---

## 8. 与其他服务的关系

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           服务依赖关系                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│                    ┌───────────────────────────┐                                │
│                    │   linkmic_understand_api  │                                │
│                    │       (本服务)            │                                │
│                    └─────────────┬─────────────┘                                │
│                                  │                                              │
│      ┌───────────────┬───────────┼───────────┬───────────────┐                  │
│      │               │           │           │               │                  │
│      ▼               ▼           ▼           ▼               ▼                  │
│ ┌─────────┐   ┌───────────┐ ┌─────────┐ ┌─────────┐   ┌───────────┐            │
│ │ EventBus│   │understand_│ │  MySQL  │ │  Redis  │   │ VikingDB  │            │
│ │         │   │   svr     │ │         │ │         │   │           │            │
│ └────┬────┘   └─────┬─────┘ └─────────┘ └─────────┘   └───────────┘            │
│      │              │                                                          │
│      │              │                                                          │
│      ▼              ▼                                                          │
│ ┌────────────────────────────┐                                                 │
│ │   linkmic_llm_data_grab    │  ← 数据准备服务                                 │
│ │   (EventBus Consumer)      │                                                 │
│ └─────────────┬──────────────┘                                                 │
│               │                                                                  │
│               ▼                                                                  │
│ ┌────────────────────────────┐                                                 │
│ │ linkmic_llm_understanding  │  ← LLM理解服务                                  │
│ │   (EventBus Consumer)      │                                                 │
│ └────────────────────────────┘                                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 关键配置项

| 配置项 | 说明 | 位置 |
|--------|------|------|
| IndicatorTypePCU | PCU指标类型 | constdef/comm.go |
| IndicatorTypeDiamonds | 钻石指标类型 | constdef/comm.go |
| CategoryBoxBattle | 盲盒对战分类 | constdef/comm.go |
| TikTokLiveMultiGuestGenerateSummary | 生成摘要Topic | constdef/eventbus.go |
| TikTokWebcastLinkmicLlmRoomCategoryAgg | 房间分类聚合Topic | constdef/eventbus.go |
| multiGuestAdminDBPSM | MySQL PSM | services/mysql.go |
