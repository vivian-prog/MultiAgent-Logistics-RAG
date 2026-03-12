# Go服务上下游链路图

## 服务概览

本文档描述了 `/Users/bytedance/GolandProjects` 目录下所有Go服务的上下游依赖关系。

| 服务名称 | 语言 | 类型 | 描述 |
|---------|------|------|------|
| linkmic_llm_data_grab | Go | EventBus Consumer + Kitex Server | 数据采集服务，负责收集直播间数据 |
| linkmic_llm_understanding | Go | EventBus Consumer + Kitex Server | LLM理解服务，负责内容理解任务 |
| linkmic_understand_api | Go | Hertz HTTP Server | HTTP API服务，提供对外接口 |
| linkmic_understand_consumer | Go | EventBus Consumer | 消费者服务，处理多种EventBus消息 |
| linkmic_understand_slice_consumer | Go | EventBus Consumer | 切片消费者服务 |
| linkmic_understand_svr | Go | Kitex RPC Server | RPC服务，提供核心能力 |
| multi_guest_interest | Python | Euler Server | 分词服务（Python实现） |
| multi_guest_interest_consumer | Go | EventBus Consumer | 兴趣点消费者服务 |

---

## 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        外部系统                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │
│  │EventBus │  │  TOS    │  │ ImageX  │  │ VCloud  │  │  SAMI   │  │   DB    │              │
│  │(MQ)     │  │(存储)   │  │(图像)   │  │(视频)   │  │(语音)   │  │(MySQL)  │              │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘              │
└───────┼────────────┼────────────┼────────────┼────────────┼────────────┼───────────────────┘
        │            │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     Go服务集群                                               │
│                                                                                             │
│  ┌──────────────────────┐      EventBus        ┌──────────────────────┐                     │
│  │linkmic_llm_data_grab │──────────────────────▶│linkmic_llm_          │                     │
│  │                      │  tiktok.webcast.      │understanding         │                     │
│  │ - EventBus Consumer  │  linkmic.llm.         │                      │                     │
│  │ - Kitex RPC Server   │  understanding        │ - EventBus Consumer  │                     │
│  │                      │                       │ - Kitex RPC Server   │                     │
│  └──────────┬───────────┘                       └──────────┬───────────┘                     │
│             │                                              │                                  │
│             │ EventBus                                      │ EventBus                         │
│             │ tiktok.webcast.linkmic.llm.result             │ tiktok.webcast.linkmic.llm.result│
│             ▼                                              ▼                                  │
│  ┌──────────────────────┐      EventBus        ┌──────────────────────┐                     │
│  │linkmic_understand_   │◀─────────────────────│linkmic_understand_   │                     │
│  │consumer              │  tiktok.live.multi_  │slice_consumer        │                     │
│  │                      │  guest.*             │                      │                     │
│  │ - EventBus Consumer  │                      │ - EventBus Consumer  │                     │
│  └──────────┬───────────┘                       └──────────┬───────────┘                     │
│             │                                              │                                  │
│             │ RPC                                          │ EventBus                         │
│             ▼                                              ▼                                  │
│  ┌──────────────────────┐      EventBus        ┌──────────────────────┐                     │
│  │linkmic_understand_svr│─────────────────────▶│multi_guest_interest_ │                     │
│  │                      │  tiktok.live.llm.    │consumer              │                     │
│  │ - Kitex RPC Server   │  slice_tag           │                      │                     │
│  └──────────┬───────────┘                       │ - EventBus Consumer  │                     │
│             │                                   └──────────┬───────────┘                     │
│             │ RPC (调用)                                    │                                  │
│             ▼                                              │                                  │
│  ┌──────────────────────┐                                 │                                  │
│  │linkmic_understand_api│                                 │                                  │
│  │                      │◀────────────────────────────────┘                                  │
│  │ - Hertz HTTP Server  │      RPC调用                                                      │
│  └──────────────────────┘                                                                    │
│                                                                                              │
│  ┌──────────────────────┐                                                                    │
│  │multi_guest_interest  │                                                                    │
│  │ (Python)             │                                                                    │
│  │ - Euler Server       │                                                                    │
│  └──────────────────────┘                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      LLM/模型服务                                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ GPT-4o / Gemini │  │ Laplace Runtime │  │ Text Embedding  │  │ Image Embedding │         │
│  │ (OpenAPI)       │  │ (ASR/Emb)       │  │ Model          │  │ Model           │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 服务详细说明

### 1. linkmic_llm_data_grab

**类型**: EventBus Consumer + Kitex RPC Server

**上游（数据来源）**:
- **EventBus**: 消费以下Topic
  - `tiktok.webcast.linkmic.llm.data_grab`
  - `tiktok.webcast.linkmic.llm.data_grab_bot`
  - `tiktok.webcast.linkmic.llm.data_grab_full`
- **Kitex RPC**: 接收RPC调用请求

**下游（数据输出）**:
- **EventBus**: 发布消息到
  - `tiktok.webcast.linkmic.llm.understanding` (理解任务)
  - `tiktok.webcast.linkmic.llm.understanding_bot`
  - `tiktok.webcast.linkmic.llm.understanding_full`
  - `tiktok.webcast.linkmic.llm.result` (结果)
  - `tiktok.webcast.linkmic.llm.result_bot`

**外部依赖**:
- **TOS**: 对象存储
- **VCloud**: 视频服务
- **Laplace Runtime**: ASR语音识别 (`tikcast.llm_model.asr_aac_v2`)
- **Text Embedding Model**: 文本向量化 (`tikcast.llm_model.emb_text_tiny`)
- **Image Embedding TRT**: 图像向量化
- **RAG Server**: 数据检索服务
- **Region SDK**: 区域识别

**数据流**:
```
EventBus消息 → 数据采集(房间信息/主播信息/评论/视频切片/音频文本/向量) → EventBus发布
```

---

### 2. linkmic_llm_understanding

**类型**: EventBus Consumer + Kitex RPC Server

**上游（数据来源）**:
- **EventBus**: 消费以下Topic
  - `tiktok.webcast.linkmic.llm.understanding`
  - `tiktok.webcast.linkmic.llm.understanding_bot`
  - `tiktok.webcast.linkmic.llm.understanding_full`
- **Kitex RPC**: 接收LLM理解请求

**下游（数据输出）**:
- **EventBus**: 发布消息到
  - `tiktok.webcast.linkmic.llm.result`
  - `tiktok.webcast.linkmic.llm.result_bot`

**外部依赖**:
- **GPT-4o / Gemini**: 通过OpenAPI调用
  - 图像描述 (ImageCaption)
  - 视频摘要 (VideoSummary)
  - 分类标注 (Classify)
  - 全文摘要 (FullTextSummarization)
- **ImageX**: 图像处理服务
- **TOS**: 对象存储
- **SAMI**: 语音服务
- **VCloud**: 视频服务
- **Laplace Runtime**: 文本向量化 (`tikcast.llm_model.emb_text_tiny`)
- **Image Embedding TRT**: 图像向量化

**核心任务**:
- 策略分类 (StrategyClassify)
- Gemini分类 (GeminiClassify)
- 全文理解 (FullTextUnderstanding)
- 输出整理 (OutputOrganize)

---

### 3. linkmic_understand_api

**类型**: Hertz HTTP Server

**上游（数据来源）**:
- **HTTP请求**: 接收外部HTTP API调用

**下游（数据输出）**:
- **EventBus**: 发布消息到多个Topic
  - `tiktok.live.multi_guest.generate_summary`
  - `tiktok.live.multi_guest.update_fragment`
  - `tiktok.webcast.linkmic.llm.room_all_fragment`
  - `tiktok.webcast.linkmic.llm.room_all_fragment_of`
  - `tiktok.webcast.linkmic.llm.room_category_agg`
  - `tiktok.webcast.linkmic.llm.anchor_category_agg`
  - `tiktok.webcast.linkmic.llm.update_asr`
  - `tiktok.webcast.linkmic.llm.annotated_dataset`
  - `tiktok.webcast.linkmic.llm.rule_trigger`
  - `tiktok.live.multi_guest.update_golden_set`
- **Kitex RPC**: 调用 `tikcast.linkmic_understand.svr`

**外部依赖**:
- **Redis**: 缓存
- **VikingDB**: 向量数据库
- **TOS**: 对象存储
- **TNS**: 内容安全服务
- **TQS**: 查询服务
- **MySQL**: 数据库
- **ElasticSearch**: 搜索引擎
- **BDSso**: 认证服务

---

### 4. linkmic_understand_consumer

**类型**: EventBus Consumer

**上游（数据来源）**:
- **EventBus**: 消费以下Topic
  - `tiktok.live.multi_guest.generate_summary`
  - `tiktok.live.multi_guest.update_fragment`
  - `tiktok.webcast.linkmic.llm.result`
  - `tiktok.webcast.linkmic.llm.result_bot`
  - `tiktok.webcast.linkmic.llm.update_asr`
  - `tiktok.webcast.linkmic.llm.rule_trigger`
  - `tiktok.live.multi_guest.update_golden_set`

**下游（数据输出）**:
- 无直接EventBus输出（处理并存储数据）

**外部依赖**:
- **Redis**: 缓存
- **TOS**: 对象存储
- **ImageX**: 图像服务
- **SAMI**: 语音服务
- **VideoIAM**: 视频权限服务
- **MySQL**: 数据库

---

### 5. linkmic_understand_slice_consumer

**类型**: EventBus Consumer

**上游（数据来源）**:
- **EventBus**: 消费以下Topic
  - `tiktok.live.llm.room_slice_2min`
  - `tiktok.live.llm.voice_txt`
  - `tiktok.live.multi_guest.generate_summary`
  - `tiktok.webcast.linkmic.llm.room_all_fragment`
  - `tiktok.webcast.linkmic.llm.room_all_fragment_of`
  - `tiktok.webcast.linkmic.llm.room_category_agg`
  - `tiktok.webcast.linkmic.llm.anchor_category_agg`
  - `tiktok.webcast.linkmic.llm.room_category_result`
  - `tiktok.webcast.multi_guest.slice_emb`

**下游（数据输出）**:
- 无直接EventBus输出

**外部依赖**:
- **TOS**: 对象存储
- **Strategy**: 策略服务
- **Region SDK**: 区域识别

---

### 6. linkmic_understand_svr

**类型**: Kitex RPC Server

**上游（数据来源）**:
- **Kitex RPC**: 接收RPC调用

**下游（数据输出）**:
- **EventBus**: 发布消息到
  - `tiktok.live.llm.slice_tag`
  - `tiktok.live.multi_guest.update_golden_set`

**外部依赖**:
- **TOS**: 对象存储
- **HDFS**: 分布式文件系统
- **Model Guardian**: 模型管理服务 (`tikcast.llm_model.guardian`)
- **RTC**: 实时通信服务
- **Lark**: 飞书通知

---

### 7. multi_guest_interest (Python)

**类型**: Euler Server (Thrift RPC)

**上游（数据来源）**:
- **Thrift RPC**: 接收分词请求

**下游（数据输出）**:
- 无直接输出

**外部依赖**:
- 无特殊外部依赖

**核心功能**:
- GetTokenization: 分词服务

---

### 8. multi_guest_interest_consumer

**类型**: EventBus Consumer

**上游（数据来源）**:
- **EventBus**: 消费以下Topic
  - `tiktok.live.llm.voice_txt`

**下游（数据输出）**:
- **EventBus**: 发布消息到
  - `tiktok.webcast.multi_guest.sync_feature`
  - `tiktok.webcast.linkmic.interest_l3center_log`

**外部依赖**:
- **Redis**: 缓存（关键词-L3中心映射）
- **TQS**: 查询服务（Hive IDF表）
- **EventBus**: 输出事件

---

## EventBus 消息流转图

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                              EventBus Topic 流转关系                                   │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  数据采集阶段                                                                          │
│  ┌─────────────────────────────┐                                                     │
│  │ tiktok.webcast.linkmic.llm  │                                                     │
│  │ .data_grab                  │──────┐                                              │
│  │ .data_grab_bot              │      │                                              │
│  │ .data_grab_full             │      ▼                                              │
│  └─────────────────────────────┘  ┌────────────────┐                                 │
│                                   │ linkmic_llm_   │                                 │
│                                   │ data_grab      │                                 │
│                                   └───────┬────────┘                                 │
│                                           │                                          │
│  理解处理阶段                              ▼                                          │
│  ┌─────────────────────────────┐  ┌────────────────┐                                 │
│  │ tiktok.webcast.linkmic.llm  │◀─│                │                                 │
│  │ .understanding              │  │ 发布消息到:     │                                 │
│  │ .understanding_bot          │  │ understanding  │                                 │
│  │ .understanding_full         │  │ result         │                                 │
│  └─────────────────────────────┘  └───────┬────────┘                                 │
│                                           │                                          │
│                                           ▼                                          │
│                                   ┌────────────────┐                                 │
│                                   │ linkmic_llm_   │                                 │
│                                   │ understanding  │                                 │
│                                   └───────┬────────┘                                 │
│                                           │                                          │
│  结果处理阶段                              ▼                                          │
│  ┌─────────────────────────────┐  ┌────────────────┐                                 │
│  │ tiktok.webcast.linkmic.llm  │◀─│ 发布消息到:     │                                 │
│  │ .result                     │  │ result         │                                 │
│  │ .result_bot                 │  │ result_bot     │                                 │
│  └─────────────────────────────┘  └───────┬────────┘                                 │
│                                           │                                          │
│                                           ▼                                          │
│                                   ┌────────────────┐                                 │
│                                   │ linkmic_       │                                 │
│                                   │ understand_    │                                 │
│                                   │ consumer       │                                 │
│                                   └────────────────┘                                 │
│                                                                                       │
│  API触发阶段                                                                          │
│  ┌─────────────────────────────┐  ┌────────────────┐                                 │
│  │ tiktok.live.multi_guest     │  │ linkmic_       │                                 │
│  │ .generate_summary           │◀─│ understand_    │                                 │
│  │ .update_fragment            │  │ api            │                                 │
│  │ .update_golden_set          │  │ (HTTP API)     │                                 │
│  └─────────────────────────────┘  └────────────────┘                                 │
│                                                                                       │
│  切片处理阶段                                                                         │
│  ┌─────────────────────────────┐  ┌────────────────┐                                 │
│  │ tiktok.live.llm             │  │ linkmic_       │                                 │
│  │ .room_slice_2min            │─▶│ understand_    │                                 │
│  │ .voice_txt                  │  │ slice_consumer │                                 │
│  └─────────────────────────────┘  └────────────────┘                                 │
│                                                                                       │
│  兴趣点处理阶段                                                                       │
│  ┌─────────────────────────────┐  ┌────────────────┐  ┌─────────────────────┐         │
│  │ tiktok.live.llm.voice_txt   │─▶│ multi_guest_   │─▶│ .sync_feature       │         │
│  │                             │  │ interest_      │  │ .interest_l3center  │         │
│  │                             │  │ consumer       │  │ _log                │         │
│  └─────────────────────────────┘  └────────────────┘  └─────────────────────┘         │
│                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## RPC调用关系图

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                 RPC调用关系                                            │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌────────────────────────────┐                                                     │
│  │ linkmic_understand_api     │                                                     │
│  │ (Hertz HTTP Server)        │                                                     │
│  └─────────────┬──────────────┘                                                     │
│                │                                                                      │
│                │ RPC调用                                                              │
│                ▼                                                                      │
│  ┌────────────────────────────┐      RPC调用        ┌────────────────────────────┐   │
│  │ linkmic_understand_svr     │────────────────────▶│ tikcast.llm_model.guardian │   │
│  │ (Kitex RPC Server)         │                     │ (模型管理服务)              │   │
│  └────────────────────────────┘                     └────────────────────────────┘   │
│                                                                                       │
│  ┌────────────────────────────┐                                                     │
│  │ linkmic_llm_data_grab      │                                                     │
│  │ (Kitex RPC Server)         │                                                     │
│  └─────────────┬──────────────┘                                                     │
│                │                                                                      │
│                ├────────────────────▶ tikcast.rag.server (RAG服务)                   │
│                ├────────────────────▶ tikcast.llm_asr.server (ASR服务)               │
│                ├────────────────────▶ tikcast.llm_model.emb_image_trt (图像向量)     │
│                └────────────────────▶ Laplace Runtime (文本向量)                      │
│                                                                                       │
│  ┌────────────────────────────┐                                                     │
│  │ linkmic_llm_understanding  │                                                     │
│  │ (Kitex RPC Server)         │                                                     │
│  └─────────────┬──────────────┘                                                     │
│                │                                                                      │
│                ├────────────────────▶ GPT-4o/Gemini (OpenAPI HTTP)                   │
│                ├────────────────────▶ ImageX (图像服务)                              │
│                ├────────────────────▶ TOS (对象存储)                                 │
│                └────────────────────▶ Laplace Runtime (向量服务)                     │
│                                                                                       │
│  ┌────────────────────────────┐                                                     │
│  │ multi_guest_interest       │                                                     │
│  │ (Python Euler Server)      │                                                     │
│  └────────────────────────────┘                                                     │
│  提供Thrift RPC接口: GetTokenization                                                  │
│                                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 外部服务依赖汇总

| 服务名称 | 数据库 | 缓存 | 对象存储 | 消息队列 | LLM服务 | 其他服务 |
|---------|--------|------|----------|----------|---------|----------|
| linkmic_llm_data_grab | - | - | TOS | EventBus | Laplace(ASR/Emb) | VCloud, RAG, Region SDK |
| linkmic_llm_understanding | MySQL | - | TOS | EventBus | GPT-4o, Gemini, Laplace | ImageX, SAMI, VCloud |
| linkmic_understand_api | MySQL, ES | Redis | TOS | EventBus | - | VikingDB, TNS, TQS, BDSso |
| linkmic_understand_consumer | MySQL | Redis | TOS | EventBus | - | ImageX, SAMI, VideoIAM |
| linkmic_understand_slice_consumer | - | - | TOS | EventBus | - | Strategy, Region SDK |
| linkmic_understand_svr | - | - | TOS | EventBus | - | HDFS, Model Guardian, RTC, Lark |
| multi_guest_interest | - | - | - | - | - | - |
| multi_guest_interest_consumer | - | Redis | - | EventBus | - | TQS(Hive) |

---

## 关键EventBus Topic说明

| Topic名称 | 生产者 | 消费者 | 用途 |
|-----------|--------|--------|------|
| tiktok.webcast.linkmic.llm.data_grab | 外部/自产 | data_grab | 数据采集任务 |
| tiktok.webcast.linkmic.llm.understanding | data_grab | understanding | LLM理解任务 |
| tiktok.webcast.linkmic.llm.result | understanding, data_grab | understand_consumer | 处理结果 |
| tiktok.live.multi_guest.generate_summary | understand_api | understand_consumer, slice_consumer | 生成摘要 |
| tiktok.live.llm.voice_txt | 外部 | slice_consumer, interest_consumer | 语音文本 |
| tiktok.webcast.multi_guest.sync_feature | interest_consumer | 外部 | 特征同步 |

---

## 服务启动顺序建议

```
1. 基础设施服务 (MySQL, Redis, TOS, EventBus)

2. 核心RPC服务:
   - linkmic_understand_svr
   - multi_guest_interest (Python)

3. 数据采集层:
   - linkmic_llm_data_grab

4. 理解处理层:
   - linkmic_llm_understanding

5. 消费者层:
   - linkmic_understand_consumer
   - linkmic_understand_slice_consumer
   - multi_guest_interest_consumer

6. API网关层:
   - linkmic_understand_api
```

---

*文档生成时间: 2026-03-05*
