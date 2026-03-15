# linkmic_understand_api 项目文档

## 1. 项目功能概述

`linkmic_understand_api` 是一个 **HTTP API 网关服务**，作为连麦直播内容理解系统的 **入口层和管理层**，主要提供：

1. **Web 管理界面 API** - 供运营/标注人员查看和管理数据
2. **飞书 Bot 接口** - 支持运维操作和通知
3. **定时任务触发** - 定时收集数据和生成报告
4. **EventBus 消息发送** - 触发下游 LLM 内容理解任务

---

## 2. 核心架构

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                 调用方                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Web 前端    │  │ 飞书 Bot    │  │ 定时任务    │  │ 内部服务    │         │
│  │ (管理后台)  │  │ (运维/运营) │  │             │  │             │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                │                 │
└─────────┼────────────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                   linkmic_understand_api (本项目)                            │
│                          HTTP API 网关                                     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  核心职责:                                                                 │
│  1. 接收 HTTP 请求，返回数据                                              │
│  2. 触发 EventBus 消息，异步执行 LLM 任务                                  │
│  3. 调用 LLM 生成评估报告                                                 │
│  4. 管理 Prompt 版本和数据集                                              │
│                                                                            │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          下游服务                                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  EventBus 消息队列:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 事件名称                              │ 消费者                      │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ tiktok.live.multi_guest.generate_summary  │ linkmic_llm_understanding │  │
│  │ tiktok.live.multi_guest.update_fragment   │ linkmic_llm_understanding │  │
│  │ tiktok.live.multi_guest.update_golden_set │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.room_all_fragment_of │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.room_category_agg   │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.anchor_category_agg │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.update_asr          │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.annotated_dataset   │ linkmic_llm_understanding │  │
│  │ tiktok.webcast.linkmic.llm.rule_trigger        │ linkmic_llm_understanding │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  RPC 服务:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ PSM                                    │ 用途                        │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ tikcast.linkmic.understand.svr         │ 音频切片获取、模型更新       │  │
│  │ tikcast.linkmic.portal                 │ 连麦记录获取                │  │
│  │ tikcast.room_sdk                       │ 房间数据获取                │  │
│  │ tikcast.rag.server                     │ RTC 切片获取               │  │
│  │ tikcast.llm.model.guardian             │ 模型服务管理               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  LLM 服务:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 模型            │ 用途                                               │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ GPT-4o-mini     │ 文本分析、分类、评估报告生成                        │  │
│  │ GPT-4-turbo     │ 多模态理解 (图片+文本)                              │  │
│  │ GPT-4o          │ 多模态理解                                         │  │
│  │ Text Embedding  │ 文本向量化 (相似性检索)                             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  存储:                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 存储            │ 用途                                               │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ MySQL           │ 房间数据、标注数据、评估指标、Prompt 版本            │  │
│  │ Redis           │ 缓存、去重、分布式锁                                │  │
│  │ Elasticsearch   │ 全文检索                                           │  │
│  │ VikingDB        │ 向量检索 (相似样本)                                 │  │
│  │ TOS             │ 对象存储                                           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 上下游依赖详解

### 3.1 上游调用方

| 调用方 | 接入方式 | 主要用途 |
|--------|----------|----------|
| **Web 管理后台** | HTTP API | 查看标注数据、修改分类、评估指标、管理数据集 |
| **飞书 Bot** | Webhook | 运维操作 (触发理解、更新模型、Golden Set 管理) |
| **定时任务** | HTTP GET | 定时收集数据集、生成评估报告、同步数据 |
| **内部服务** | HTTP API | 数据查询、触发任务、同步数据 |

### 3.2 下游服务依赖

#### EventBus 消息 (发送到 linkmic_llm_understanding 消费)

| 事件名称 | 触发场景 |
|----------|----------|
| `tiktok.live.multi_guest.generate_summary` | 触发内容理解任务 |
| `tiktok.live.multi_guest.update_fragment` | 更新片段数据 |
| `tiktok.live.multi_guest.update_golden_set` | 更新 Golden Set |
| `tiktok.webcast.linkmic.llm.room_all_fragment_of` | 房间片段聚合 |
| `tiktok.webcast.linkmic.llm.room_category_agg` | 房间分类聚合 |
| `tiktok.webcast.linkmic.llm.anchor_category_agg` | 主播分类聚合 |
| `tiktok.webcast.linkmic.llm.update_asr` | 更新 ASR |
| `tiktok.webcast.linkmic.llm.annotated_dataset` | 标注数据集 |
| `tiktok.webcast.linkmic.llm.rule_trigger` | 规则触发 |

#### RPC 服务

| 服务 PSM | 用途 |
|----------|------|
| `tikcast.linkmic.understand.svr` | 音频切片获取、模型更新通知、检查新模型 |
| `tikcast.linkmic.portal` | 获取连麦记录 |
| `tikcast.room_sdk` | 房间数据、主播数据、在线房间 |
| `tikcast.rag.server` | RTC 切片数据获取 |
| `tikcast.llm.model.guardian` | 模型服务更新 |
| `tikcast.room_traffic_stats` | 房间流量指标 |

#### LLM 服务

| 模型 | 用途 | 调用位置 |
|------|------|----------|
| GPT-4o-mini | 文本分析、分类评估、话题评估、质量评估、氛围评估、舆情评估 | `evaluation/*.go` |
| GPT-4-turbo | 多模态理解 (图片/视频+文本) | `llmservices/gpt4turbov.go` |
| Text Embedding | 文本向量化，用于相似性检索 | `llmservices/api.go` |

### 3.3 存储依赖

| 存储 | 用途 | 相关文件 |
|------|------|----------|
| MySQL | 房间数据、标注数据、评估指标 | `services/mg_*.go` |
| Redis | 缓存、去重、分布式锁 | `services/redis.go` |
| Elasticsearch | 全文检索 | `services/es.go` |
| VikingDB | 向量检索 (相似样本) | `services/vikingdb.go` |
| TOS | 对象存储 | `services/tos.go` |

---

## 4. 核心 API 接口

### 4.1 Web API (`/api/linkmic_understand_web/`)

| 接口 | 方法 | 功能 |
|------|------|------|
| `generate_understand` | POST | 触发内容理解任务 |
| `get_fragment` | POST | 获取片段详情 |
| `get_fragment_batch` | POST | 批量获取片段 |
| `modify_category` | POST | 修改分类标注 (需登录) |
| `modify_category_batch` | POST | 批量修改分类 |
| `modify_remark` | POST | 修改备注 |
| `get_record` | POST | 获取记录 |
| `get_evaluation_metrics` | POST | 获取评估指标 |
| `get_dataset` | POST | 获取数据集 |
| `create_prompt_version` | POST | 创建 Prompt 版本 (需登录) |
| `get_prompt_version_batch` | POST | 获取 Prompt 版本 |
| `get_similar_sample` | GET | 获取相似样本 (向量检索) |
| `batch_classify_llm_play_tag` | POST | 批量 LLM 分类 |
| `batch_set_fragment_test_set` | POST | 设置测试集 |
| `timer_collect_dataset` | GET | 定时收集数据集 |
| `timer_evaluation_generate` | GET | 定时生成评估 |
| `timer_evaluation_metrics` | GET | 定时计算指标 |

### 4.2 Pipeline API (`/api/linkmic_understand_pipeline/`)

| 接口 | 方法 | 功能 |
|------|------|------|
| `rule_prod` | GET | 生产规则 |
| `check_new_model` | GET | 检查新模型 |
| `monitor_matrix` | GET | 监控混淆矩阵 |
| `monitor_distribution` | GET | 监控分布 |
| `create_tcs_task` | GET/POST | 创建 TCS 审核任务 |

### 4.3 Bot API (`/api/linkmic_understand_bot/`)

| 接口 | 方法 | 功能 |
|------|------|------|
| `message` | POST | 飞书消息回调 |
| `test` | GET | 测试接口 |
| `evaluation` | GET | 触发评估报告生成 |

### 4.4 In API (`/api/linkmic_understand_in/`) - 内部接口

| 接口 | 功能 |
|------|------|
| `generate_summary` | 触发内容理解 |
| `update_fragment` | 更新片段 |
| `get_host_progress` | 获取主播进度 |
| `room_all_fragment` | 房间所有片段 |
| `room_category_agg` | 房间分类聚合 |
| `anchor_category_agg` | 主播分类聚合 |
| `get_similar_sample2` | 相似样本检索 |

---

## 5. LLM 使用场景

### 5.1 评估报告生成 (`evaluation/`)

本项目直接调用 LLM 生成多维度评估报告：

| 模块 | 文件 | 功能 |
|------|------|------|
| 玩法分类评估 | `category_prompt.go` | 分析 Others 类别内容 |
| 内容质量评估 | `quality_prompt.go` | 评估优质/低质/普通 |
| 话题评估 | `topic_prompt.go` | 分析讨论话题 |
| 氛围评估 | `atmosphere_prompt.go` | 分析直播间氛围 |
| 舆情评估 | `opinion_prompt.go` | 分析用户观点 |
| 报告合并 | `merge_prompt.go` | 合并所有评估报告 |

### 5.2 LLM 调用方式

```go
// 文本到文本 (评估报告生成)
llmservices.CallGPT4Txt2TxtWithLimit(
    gpt4Msg,       // prompt 消息
    logID,         // 日志 ID
    "gpt-4o-mini", // 模型名称
    2000,          // max_tokens
    0.5,           // temperature
    host, ak       // 服务地址和密钥
)

// 多模态 (图片/视频理解)
llmservices.CallGPTMM2TxtWithLimit(
    gptvMsg,       // 包含图片 URL 的消息
    logID,
    "gpt-4-turbo", // 或 gpt-4o
    0.5,
    4096,
    host, ak,
)

// 文本嵌入 (相似性检索)
llmservices.CallGPTTextEmbeddingWithLimit(
    text,          // 待向量化文本
    logID,
    "text-embedding-3-large",
    3072,          // dimensions
    host, ak,
)
```

---

## 6. 与其他服务的关系

### 6.1 与 linkmic_llm_understanding 的关系

```
┌───────────────────────────────────────────────────────────────────┐
│                     linkmic_understand_api                         │
│                        (本项目 - API 层)                           │
│                                                                   │
│  • 接收 HTTP 请求                                                 │
│  • 发送 EventBus 消息                                             │
│  • 调用 LLM 生成评估报告                                          │
│  • 管理 Prompt 版本                                              │
│  • Web 管理界面支持                                               │
└───────────────────────────────┬───────────────────────────────────┘
                                │ EventBus
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                   linkmic_llm_understanding                        │
│                      (消费者 - 计算层)                             │
│                                                                   │
│  • 消费 EventBus 消息                                             │
│  • 执行 LLM 内容理解 (视频 Caption、分类)                          │
│  • RAG Few-Shot 召回                                             │
│  • 写入数据库                                                     │
└───────────────────────────────────────────────────────────────────┘
```

**分工**:
- `linkmic_understand_api` (本项目): **API 层**，负责请求入口、触发任务、评估报告生成、管理功能
- `linkmic_llm_understanding`: **计算层**，负责执行 LLM 内容理解任务

### 6.2 与 linkmic_understand_svr 的关系

```
┌───────────────────────────────────────────────────────────────────┐
│                     linkmic_understand_api                         │
│                        (本项目)                                   │
└───────────────────────────────┬───────────────────────────────────┘
                                │ RPC 调用
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                   linkmic_understand_svr                           │
│                       (RPC 服务)                                  │
│                                                                   │
│  • OperateFile: 获取音频切片                                     │
│  • NotifyModelUpdate: 通知模型更新                               │
│  • CheckNewModel: 检查新模型                                     │
│  • GetAllSelectedRoom: 获取选中房间                              │
│  • TCS 回调处理                                                  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 7. 配置管理

### TCC 配置

| 配置 Key | 用途 |
|----------|------|
| GPT 相关 | LLM 服务地址和 AK |
| TNS | TNS 服务配置 |
| VikingDB | 向量检索配置 |

---

## 8. 部署说明

- 框架: Hertz (HTTP)
- 运行环境: 仅在 `DC_MALIVA` 机房启用 EventBus 发送
- 会话认证: BDSSO
