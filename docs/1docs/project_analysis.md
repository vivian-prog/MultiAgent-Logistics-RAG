# linkmic_llm_understanding 项目分析

## 1. 项目目的

这是一个 **LLM 内容理解服务**，用于对直播内容进行智能分析和分类。主要功能包括：

- **直播内容理解**：通过 LLM 对直播视频片段进行分析，生成内容摘要和分类
- **多模态处理**：支持视频、音频(ASR)、图片、评论等多种数据类型的处理
- **内容分类**：将直播内容分类到不同类别（如聊天、游戏等）
- **结果推送**：将处理结果通过 EventBus 推送给下游消费者

---

## 2. 代码链路

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              入口层 (main.go)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. EventBus Consumer (3个)                                                  │
│     - UnderstandingEventName (常规)                                          │
│     - UnderstandingForBotEventName (Bot专用)                                 │
│     - UnderstandingForFullEventName (完整处理)                               │
│                                                                              │
│  2. Kitex RPC Server                                                         │
│     - LLMUnderstandingServiceImpl.PushTask()                                 │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        消费者处理层 (consumer/)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  EventHandler() → understandingSvc.ProcessTask()                             │
│                                                                              │
│  根据任务类型选择处理链：                                                       │
│  - understandingMethod=0: GeminiClassifyTask → OutputOrganizeTask           │
│  - understandingMethod=1: StrategyClassifyTask → OutputOrganizeTask         │
│  - FullTextUnderstanding: FullTextUnderstandingTask → OutputOrganizeTask    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         任务层 (tasks/)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Task接口: Do(ctx, taskItem, plugin, evtName) → []*InformationBlock         │
│                                                                              │
│  主要任务实现：                                                                │
│  ├── GeminiClassifyTask     - Gemini模型分类任务                             │
│  ├── StrategyClassifyTask   - 策略分类任务（支持Matx/SDK两种模式）             │
│  ├── FullTextSummarization  - 全文摘要任务                                   │
│  ├── ImageCaptionTask       - 图片描述任务                                   │
│  ├── VideoSummaryTask       - 视频摘要任务                                   │
│  └── OutputOrganizeTask     - 输出整理任务（最终输出）                         │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LLM调用层 (llm_calling/)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  GameplayEvaluationAccessor - 访问器模式，封装LLM调用流程                      │
│                                                                              │
│  主要函数：                                                                   │
│  ├── GenerateLLMCaption()   - 生成视频/图片描述                              │
│  ├── LLMClassify()          - LLM分类（使用Few-Shot学习）                    │
│  ├── RecallFewShot()        - RAG召回相似样本                                │
│  └── TakeMeOutClassify()    - TMO分类（特殊场景）                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         插件层 (plugins/)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Plugin接口 - 定义各种Prompt生成方法                                          │
│                                                                              │
│  AnchorClassification实现：                                                   │
│  ├── GeminiSummaryPrompts()       - 生成Gemini摘要Prompt                     │
│  ├── StrategyClassifyPrompts()    - 生成策略分类Prompt                       │
│  ├── ImageCaptionPrompts()        - 生成图片描述Prompt                       │
│  └── OutputOrganize()             - 整理输出格式                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      外部服务调用层 (clients/)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ModelAdapter - LLM模型适配器                                                 │
│  ├── GeminiClassify()      → GPT/Gemini多模态API                            │
│  ├── ImageCaption()        → 图片转文字API                                   │
│  └── Understanding()       → 文本理解API                                     │
│                                                                              │
│  其他客户端：                                                                 │
│  ├── ImageX      - 图片处理服务                                              │
│  ├── TOS         - 对象存储服务                                              │
│  ├── VCloud      - 视频云服务                                                │
│  ├── SAMI        - 语音识别服务                                              │
│  └── Fornax      - Prompt管理服务                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 主要方法

| 方法位置 | 方法名 | 功能描述 |
|---------|--------|----------|
| `main.go:36` | `EventHandler()` | EventBus消息处理入口 |
| `handler.go:17` | `PushTask()` | Kitex RPC入口，接收任务请求 |
| `understanding_service.go:81` | `ProcessTask()` | 核心任务处理逻辑 |
| `gemini_classify.go:27` | `GeminiClassifyTask.Do()` | Gemini分类任务执行 |
| `strategy_classify.go:46` | `StrategyClassifyTask.Do()` | 策略分类任务执行 |
| `strategy_classify.go:118` | `CallMatxInference()` | 调用Matx推理模型 |
| `strategy_classify.go:169` | `CallSDK()` | 调用LLM调度SDK |
| `accessor.go:81` | `Visit()` | 访问器模式执行LLM调用链 |
| `fn_llm_calling.go:93` | `LLMClassify()` | LLM分类（含Few-Shot） |
| `fn_rag.go` | `RecallFewShot()` | RAG召回相似样本 |
| `rpc_model_adapter.go:216` | `GeminiClassify()` | Gemini模型调用适配 |

---

## 4. 实现方式

### 4.1 架构模式

- **微服务架构**：基于 Kitex RPC 框架
- **事件驱动**：使用 EventBus 进行异步消息处理
- **插件模式**：通过 Plugin 接口实现不同业务场景的 Prompt 生成
- **责任链模式**：Task 按顺序执行，前一个 Task 的输出作为后一个的输入
- **访问器模式**：`GameplayEvaluationAccessor` 封装复杂的数据访问和LLM调用流程

### 4.2 数据流

```
TaskItem (输入)
    ├── DataBlocks[] - 数据块列表
    │   ├── VideoSliceDataBlock    - 视频片段
    │   ├── AudioTextDataBlock     - ASR文本
    │   ├── RoomDataBlock          - 房间信息
    │   └── CommentsDataBlock      - 评论数据
    │
    └── Understanding配置
        ├── understandingMethod    - 处理方法选择
        └── fullTextUnderstanding  - 是否全文理解

                    ↓ 处理

InformationBlock[] (输出)
    ├── DataUnderstanding         - 理解结果
    └── DataFinalOutput           - 最终输出
```

### 4.3 关键技术

| 技术 | 用途 |
|------|------|
| Kitex | RPC服务框架 |
| EventBus | 消息队列（消费任务/推送结果） |
| GPT-4o/Gemini | 多模态LLM模型 |
| Fornax | Prompt模板管理 |
| Laplace | 模型推理服务 |
| TOS | 对象存储（视频/图片） |
| TCC | 动态配置管理 |
| GORM/GEN | 数据库ORM |

### 4.4 分类流程

```
1. GeminiClassifyTask (默认流程):
   GenerateLLMCaption → RecallFewShot → LLMClassify → OutputOrganize

2. StrategyClassifyTask (策略分类):
   根据配置选择:
   - mode=0: MatxInference
   - mode=1: SDK调用
   - mode=2: MatxInference + SDK 混合

3. FullTextUnderstanding:
   全文摘要 + 输出整理
```

### 4.5 容错与重试

- LLM调用支持5次重试，针对频控错误自动等待后重试
- panic恢复机制，防止服务崩溃
- 错误状态码和消息记录到TaskInfo

---

## 5. 核心处理流程详解

### 5.1 GeminiClassifyTask 流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      GeminiClassifyTask 完整流程                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Step 1: 数据准备 (NewCaseAccessorFromTaskItem)                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: TaskItem (包含 DataBlocks)                                           │ │
│  │  处理:                                                                       │ │
│  │  • 解析 VideoSliceDataBlock → 获取视频URI                                   │ │
│  │  • 解析 DivAudioSliceAndTextDataBlock → 获取分流ASR (UserID→Text映射)       │ │
│  │  • 解析 RoomDataBlock → 获取房间信息(Title, Sticker, AnchorID等)            │ │
│  │  • 解析 CommentsDataBlock → 获取评论数据                                    │ │
│  │  • 解析 EmbeddingBlock → 获取预计算的向量                                    │ │
│  │  输出: GameplayEvaluationAccessor                                           │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 2: GenerateLLMCaption (生成视频摘要)                                       │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: 视频/图片数据                                                         │ │
│  │  处理:                                                                       │ │
│  │  • 调用 plugin.GeminiSummaryPrompts() 生成Prompt                            │ │
│  │  • 下载视频文件 (TOS)                                                        │ │
│  │  • Base64编码视频                                                           │ │
│  │  • 调用 ModelAdapter.GeminiClassify() (GPT-4o/Gemini API)                   │ │
│  │  输出: LlmVideoCaption (视频内容摘要)                                        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 3: RecallFewShot (RAG召回相似样本) - 可选                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: LlmVideoCaption                                                      │ │
│  │  处理:                                                                       │ │
│  │  • 获取 caption 的 Embedding 向量                                           │ │
│  │  • 从 VikingDB 向量数据库召回 TopK 相似文档                                   │ │
│  │  • LLM Re-rank 重排序，选择最相关的样本                                       │ │
│  │  • 从数据库获取 FewShot 样本的详细数据                                        │ │
│  │  输出: FewShotID (相似样本ID列表)                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 4: LLMClassify (LLM分类)                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: Title + Sticker + VideoCaption + FewShot样本                         │ │
│  │  处理:                                                                       │ │
│  │  • 构建 Few-Shot Prompt (包含相似样本的Title/Summary/Category)              │ │
│  │  • 调用 Fornax.ExecutePromptLocal() 执行分类Prompt                           │ │
│  │  • 解析 LLM 返回的分类结果                                                   │ │
│  │  输出: LlmCategory, LlmCategoryReason, LlmCategoryPossibility               │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 5: OutputOrganize (输出整理)                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: 所有处理结果                                                          │ │
│  │  处理:                                                                       │ │
│  │  • 整合 BasicInfo (ID, RoomID, AnchorID, Title等)                           │ │
│  │  • 整合 MediaInfo (VideoUrl, ImageUrls, AudioText)                         │ │
│  │  • 整合 LlmInfo (Category, Topic, Reason)                                  │ │
│  │  • 整合 StrategyInfo (分类分数分布)                                         │ │
│  │  输出: JSON格式的最终结果                                                   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 StrategyClassifyTask 流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     StrategyClassifyTask 分类流程                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Step 1: 数据准备                                                               │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输入: TaskItem                                                              │ │
│  │  处理: 解析各类 DataBlock，构建 LiveFragment 结构                             │ │
│  │  • 提取 Title, Sticker                                                      │ │
│  │  • 提取 ASR 文本 (分流ASR优先)                                               │ │
│  │  • 提取评论 (按时间排序)                                                     │ │
│  │  • 提取图片URL                                                              │ │
│  │  • 生成 Embedding 向量 (Title+Sticker, ASR, Image)                          │ │
│  │  输出: LiveFragment                                                          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 2: 分类模式选择 (根据TCC配置)                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  mode = 0: CallMatxInference                                                │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
│  │  │  • 调用 Laplace MatxInference API                                       │  │ │
│  │  │  • 使用 StrategyClassifyModel 配置的模型                                │  │ │
│  │  │  • 返回分类结果和分数分布                                                │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                              │ │
│  │  mode = 1: CallSDK                                                          │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
│  │  │  • 调用 llm_global_scheduling SDK                                       │  │ │
│  │  │  • 使用 SocialClassifierV3 模型                                         │  │ │
│  │  │  • 输入: Title+Sticker, ASR, Image 三模态                               │  │ │
│  │  │  • 返回多标签分类结果                                                    │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                              │ │
│  │  mode = 2: 混合模式                                                          │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
│  │  │  • 先调用 MatxInference                                                 │  │ │
│  │  │  • 如果结果不是 BoxBattle，再调用 SDK                                    │  │ │
│  │  │  • 如果 SDK 结果是 BoxBattle，则修正为 NoGameplay                        │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Step 3: 结果封装                                                               │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  输出: GPT4Text 结构                                                         │ │
│  │  {                                                                           │ │
│  │    "category": "BoxBattle",           // 最高分分类                          │ │
│  │    "score": 0.95,                     // 最高分                              │ │
│  │    "category_probs": [                // 分类分数分布                         │ │
│  │      {"text": "BoxBattle", "score": 0.95},                                   │ │
│  │      {"text": "TalentShow", "score": 0.03}                                   │ │
│  │    ]                                                                         │ │
│  │  }                                                                           │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. RAG Few-Shot 学习机制

### 6.1 作用

通过向量检索召回相似的历史样本，作为 Few-Shot 示例提供给 LLM，提升分类准确性。

### 6.2 流程

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          RAG Few-Shot 检索流程                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│  │ 当前视频摘要  │───▶│ Embedding生成 │───▶│ VikingDB检索 │                      │
│  │ (VideoCaption)│    │ (文本向量化)   │    │ (TopK相似文档)│                      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                      │
│                                                   │                              │
│                                                   ▼                              │
│                                          ┌──────────────┐                      │
│                                          │ LLM Re-rank │                      │
│                                          │ (相关性重排序) │                      │
│                                          └──────┬───────┘                      │
│                                                   │                              │
│                                                   ▼                              │
│                                          ┌──────────────┐                      │
│                                          │ 数据库查询   │                      │
│                                          │ 获取样本详情  │                      │
│                                          └──────┬───────┘                      │
│                                                   │                              │
│                                                   ▼                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                     Few-Shot Prompt 构建                                   │  │
│  │  ### Examples                                                              │  │
│  │                                                                             │  │
│  │  <Title>xxx</Title><Video Summary>xxx</Video Summary>                     │  │
│  │  <category>BoxBattle</category>                                            │  │
│  │                                                                             │  │
│  │  ----Example Split----                                                     │  │
│  │                                                                             │  │
│  │  <Title>yyy</Title><Video Summary>yyy</Video Summary>                     │  │
│  │  <category>TalentShow</category>                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 配置项

| 配置 | 说明 | 默认值 |
|------|------|--------|
| EnableRAGFewShot | 是否启用RAG Few-Shot | false |
| FewShotVikingIndex.Index | VikingDB索引名 | - |
| FewShotVikingIndex.TopK | 召回数量 | 10 |
| PromptClassify | 分类Prompt配置 | - |

---

## 7. 分类标签体系

### 7.1 一级分类

| 分类 | 英文名 | 说明 |
|------|--------|------|
| 盲盒对战 | BoxBattle | 玩家对战类玩法 |
| 才艺展示 | TalentShow | 音乐/舞蹈/艺术表演 |
| 咨询 | Consulting | 法律/情感/健康咨询 |
| 约会 | Dating | 相亲/交友 |
| 辩论 | Debating | 话题辩论 |
| 非玩法 | NoGameplay | 普通聊天无特殊玩法 |
| 未覆盖 | UnCovered | 未覆盖的场景 |
| 废弃 | Abandon | 废弃数据 |

### 7.2 二级分类示例

```
TalentShow (才艺展示)
├── Music        (音乐)
├── DJ           (DJ打碟)
├── Dance        (舞蹈)
├── Art          (艺术)
└── OtherTalents (其他才艺)

Consulting (咨询)
├── Relationship             (情感关系)
├── Law                      (法律咨询)
├── MetaphysicalConsultation (玄学咨询)
├── Health                   (健康咨询)
├── PersonalDevelopment      (个人发展)
├── Finance&Wealth           (财经)
└── OtherService             (其他服务)

Debating (辩论)
├── Relationship          (情感话题)
├── SexualOrientation     (性取向)
├── Politics&Society      (政治社会)
├── Entertainment&Culture (娱乐文化)
├── Religion              (宗教)
├── PersonalExperience    (个人经历)
└── OtherTopics           (其他话题)
```

---

## 8. TCC 动态配置

### 8.1 主要配置项

| 配置Key | 配置结构 | 用途 |
|---------|----------|------|
| `model_name` | ModelNameConfig | LLM模型名称配置 |
| `common` | CommonConfig | 通用配置(分类模式等) |
| `golden_set` | GoldenSetConfig | Golden Set和RAG配置 |
| `score_threshold` | map[string]float64 | 分类分数阈值 |
| `video` | VideoConfig | 视频服务配置 |
| `sami` | SamiConfig | SAMI语音服务配置 |
| `tos` | map[string]*TOSConfig | TOS存储配置 |

### 8.2 ModelNameConfig 结构

```go
type ModelNameConfig struct {
    ImageCaptionModel          string  // 图片描述模型: gpt-4o-2024-05-13
    VideoDescModel             string  // 视频描述模型
    ClassifyModel              string  // 分类模型
    SummarizeAndClassifyModel  string  // 摘要+分类模型
    FullTextSummarizationModel string  // 全文摘要模型: gpt-4o-mini
    FullTextImageModel         string  // 全文图片模型
    VideoClassifyModel         string  // 视频分类模型: gemini-2.5-pro
}
```

### 8.3 CommonConfig 结构

```go
type CommonConfig struct {
    UnderstandOnlyMultiAsr bool    // 是否只使用多人ASR
    StrategyClassifyModel  string  // 策略分类模型名
    StrategyClassifyMode   int     // 分类模式: 0-Laplace, 1-SDK, 2-混合
}
```

---

## 9. 外部服务依赖

### 9.1 LLM服务

| 服务 | 用途 | 调用方式 |
|------|------|----------|
| GPT-4o API | 多模态理解 | HTTP API |
| Gemini 2.5 Pro | 视频分类 | HTTP API |
| Fornax | Prompt模板管理 | RPC |
| Laplace | 模型推理服务 | RPC |
| VikingDB | 向量检索(RAG) | SDK |

### 9.2 基础设施

| 服务 | 用途 |
|------|------|
| EventBus | 任务消费/结果推送 |
| TOS | 视频/图片存储 |
| MySQL | 数据持久化 |
| TCC | 动态配置 |

---

## 10. 数据库表结构

### 10.1 主要表

| 表名 | 用途 |
|------|------|
| `gameplay_evaluation` | 游戏玩法评估记录(包含视频摘要、分类结果) |
| `multi_guest_room_fragment_material` | 多人直播片段素材(包含视频URI、ASR、评论) |

### 10.2 gameplay_evaluation 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int64 | 主键 |
| fragment_id | int64 | 片段ID |
| llm_video_caption | text | LLM生成的视频摘要 |
| llm_category | varchar | LLM分类结果 |
| llm_category_reason | text | 分类原因 |
| final_category | varchar | 最终分类(人工校正后) |
| caption_prompt_key | varchar | 使用的Prompt Key |
| caption_prompt_version | string | Prompt版本 |
