# tiktok.live.multi_guest.generate_summary 完整链路

## 概述

本文档描述 `tiktok.live.multi_guest.generate_summary` 消息从生产到消费的完整链路。

---

## 消息结构

### GenerateSummaryMsg

```go
type GenerateSummaryMsg struct {
    RoomID           int64          // 房间ID（必填）
    IndicatorTime    int64          // 指标时间点（0表示自动选取）
    IndicatorType    string         // 指标类型
    LarkBotMessageID string         // Lark Bot 消息ID（非空时使用 Bot 通道）
    InitType         int64          // 初始化类型（1:LLM, 2:伪人工, 3:策略）
    Refresh          int            // 是否强制刷新（1:强制）
    Type             string         // 类型（"understand":整场理解）
    SurveyCategory   string         // 调研分类
    SourceType       TaskSourceType // 来源类型
}
```

### 示例消息

```json
{
    "room_id": 7561216058309954324,
    "indicator_time": 0,
    "indicator_type": "PCU",
    "lark_bot_message_id": "",
    "init_type": 0,
    "refresh": 0,
    "type": "",
    "survey_category": "",
    "source_type": "top_live_hot"
}
```

### 字段说明

| 字段 | 值 | 含义 |
|------|-----|------|
| room_id | 7561216058309954324 | 直播间ID |
| indicator_time | 0 | 未指定具体时间点，系统自动选取 |
| indicator_type | PCU | 按峰值在线人数选取片段 |
| lark_bot_message_id | "" | 非Bot触发 |
| init_type | 0 | 普通初始化 |
| refresh | 0 | 非强制刷新 |
| type | "" | 非整场理解模式（片段理解模式） |
| survey_category | "" | 无调研分类 |
| source_type | top_live_hot | 来源：热门直播 |

---

## 完整链路图

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           tiktok.live.multi_guest.generate_summary 链路                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│ 生产者            │
│ linkmic_understand│
│ _api             │
│ (HTTP API/定时器) │
└────────┬─────────┘
         │ 发送消息
         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ EventBus Topic: tiktok.live.multi_guest.generate_summary                                 │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ 消费者            │
│ linkmic_understand│
│ _consumer        │
│ handler.go:16-17 │
└────────┬─────────┘
         │ EventHandler 路由
         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ HandleNewGenerateSummary (new_generate_summary.go:21)                                    │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  1. 解析消息 → msg.RoomID = 7561216058309954324                                          │
│                                                                                          │
│  2. 判断 type != "understand" → 走片段理解模式                                            │
│                                                                                          │
│  3. indicator_time == 0 → 使用 indicator_type = "PCU"                                    │
│                                                                                          │
│  4. GetMultiGuestRoomFragmentMaterial(room_id, "PCU")                                    │
│     ↓                                                                                    │
│     ┌─────────────────────────────────────┐                                              │
│     │ 查询 multi_guest_room_fragment_material 表                            │
│     │ 是否有预准备的素材？                    │                                              │
│     └─────────────────────────────────────┘                                              │
│              │                                                                           │
│              ├── 有素材 → sendUnderstandWithMaterial                                     │
│              │                                                                           │
│              └── 无素材 → sendUnderstand ← 本例走这个路径                                 │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼ (无素材路径)
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ sendUnderstand (new_generate_summary.go:205-365)                                         │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  Step 1: GetRoomData(room_id)                                                            │
│  ├── 调用 live.room.live_record_tiktok 服务                                               │
│  ├── 获取直播间基础信息 (anchor_id, create_time, finish_time)                              │
│  └── 检查是否在30天内                                                                     │
│                                                                                          │
│  Step 2: GetRoomLinkRecords(room_id, start, end)                                         │
│  ├── 获取连麦记录                                                                         │
│  └── FilterLinkRecordsWithMulti → 过滤多嘉宾连麦                                           │
│                                                                                          │
│  Step 3: 获取指标趋势 (因为 indicator_time == 0)                                           │
│  ├── GetPCUTrends() → PCU趋势数据                                                        │
│  ├── GetDiamondsTrends() → 钻石趋势数据                                                   │
│  ├── GetFollowUVTrends() → 关注趋势数据                                                   │
│  ├── GetSendGiftUVTrends() → 送礼趋势数据                                                 │
│  └── GetCommentUVTrends() → 评论趋势数据                                                  │
│                                                                                          │
│  Step 4: getLinkMaxIndicator() → 计算各指标在连麦期间的峰值时间                              │
│  ├── maxPcuTime = PCU峰值时间                                                            │
│  ├── maxDiamondsTime = 钻石峰值时间                                                       │
│  └── ...                                                                                 │
│                                                                                          │
│  Step 5: 选择 indicator_time                                                             │
│  ├── indicator_type == "PCU" → 使用 maxPcuTime                                           │
│  └── indicator_time = 1760487720 (假设PCU峰值时间)                                         │
│                                                                                          │
│  Step 6: 构建 TaskItem                                                                   │
│  ├── TaskInfo: AnchorID, RoomID, Extra(包含指标信息)                                       │
│  ├── DataGrab: 需要采集的数据                                                             │
│  │   ├── AnchorInformation: true                                                        │
│  │   ├── RoomInformation: true                                                          │
│  │   ├── VideoSlice: true (时间范围: indicator_time ± 60秒)                              │
│  │   ├── Comments: true                                                                 │
│  │   ├── DivAudioSliceAndText: true (分离音频)                                           │
│  │   └── Embedding: true                                                                │
│  └── Understanding: NeedVideoSummary, NeedImageCaption, Understanding: true             │
│                                                                                          │
│  Step 7: 发送消息                                                                         │
│  └── SendDataGrabMsg(taskItem) → tiktok.webcast.linkmic.llm.data_grab                    │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ EventBus Topic: tiktok.webcast.linkmic.llm.data_grab                                     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ linkmic_llm_     │
│ data_grab        │
│ (数据采集服务)    │
└────────┬─────────┘
         │ 采集: 房间信息/主播信息/视频切片/音频文本/评论/向量
         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ EventBus Topic: tiktok.webcast.linkmic.llm.understanding                                 │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ linkmic_llm_     │
│ understanding    │
│ (LLM理解服务)     │
└────────┬─────────┘
         │ 执行: VideoSummary, ImageCaption, Classify, FullTextSummarization
         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ EventBus Topic: tiktok.webcast.linkmic.llm.result                                        │
└──────────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ linkmic_understand│
│ _consumer        │
│ (存储结果)        │
└──────────────────┘
```

---

## 链路阶段详解

### 阶段1: 生产者 (linkmic_understand_api)

**触发方式**:
- HTTP API 调用
- 定时器触发 (ByteFaaS Timer Event)

**代码位置**: `linkmic_understand_api/handler/trigger.go:58-59`

```go
if eventName == "generate_summary" {
    _, _ = in.GenerateSummary(inCtx)
}
```

### 阶段2: 消费者路由 (linkmic_understand_consumer)

**代码位置**: `linkmic_understand_consumer/handler.go:16-17`

```go
case constdef.TikTokLiveMultiGuestGenerateSummary:
    return handler.HandleNewGenerateSummary(ctx, event)
```

### 阶段3: 消息处理 (HandleNewGenerateSummary)

**代码位置**: `linkmic_understand_consumer/handler/new_generate_summary.go:21-87`

**处理流程**:

```
解析消息
    │
    ▼
判断处理模式
├── type == "understand" → 整场理解模式
└── type == "" → 片段理解模式 ← 本例
    │
    ▼
查询预准备素材
├── 有素材 → sendUnderstandWithMaterial
└── 无素材 → sendUnderstand ← 本例
```

### 阶段4: 片段选取 (sendUnderstand)

**代码位置**: `linkmic_understand_consumer/handler/new_generate_summary.go:205-365`

**核心步骤**:

| 步骤 | 函数 | 说明 |
|------|------|------|
| 1 | GetRoomData | 获取直播间基础信息 |
| 2 | GetRoomLinkRecords | 获取连麦记录 |
| 3 | FilterLinkRecordsWithMulti | 过滤多嘉宾连麦 |
| 4 | GetPCUTrends 等 | 获取各指标趋势数据 |
| 5 | getLinkMaxIndicator | 计算连麦期间峰值时间 |
| 6 | 构建TaskItem | 组装任务数据 |
| 7 | SendDataGrabMsg | 发送到数据采集Topic |

### 阶段5: 数据采集 (linkmic_llm_data_grab)

**Topic**: `tiktok.webcast.linkmic.llm.data_grab`

**采集内容**:
- 主播信息 (AnchorInformation)
- 房间信息 (RoomInformation)
- 视频切片 (VideoSlice): indicator_time ± 60秒
- 评论数据 (Comments)
- 分离音频文本 (DivAudioSliceAndText)
- 向量嵌入 (Embedding)

### 阶段6: LLM理解 (linkmic_llm_understanding)

**Topic**: `tiktok.webcast.linkmic.llm.understanding`

**理解任务**:
- VideoSummary: 视频摘要
- ImageCaption: 图像描述
- Classify: 内容分类
- FullTextSummarization: 全文摘要

### 阶段7: 结果存储 (linkmic_understand_consumer)

**Topic**: `tiktok.webcast.linkmic.llm.result`

**存储内容**:
- 分类结果 (llm_category, strategy_category)
- 摘要内容
- 向量数据

---

## 发送到 data_grab 的 TaskItem 示例

```json
{
  "task_info": {
    "task_type": "TaskGenerating",
    "anchor_id": 6940108081117512706,
    "room_id": 7561216058309954324,
    "extra": "{\"anchor_id\":6940108081117512706,\"room_id\":7561216058309954324,\"indicator_type\":\"PCU\",\"indicator_value\":15000,\"indicator_time\":1760487720,\"task_type\":\"generate_summary\",\"source_type\":\"top_live_hot\"}"
  },
  "data_grab": {
    "anchor_information": true,
    "room_information": true,
    "video_slice": true,
    "video_time_ranges": [
      {"start": 1760487660, "end": 1760487780}
    ],
    "comments": true,
    "comment_time_ranges": [
      {"start": 1760487660, "end": 1760487780}
    ],
    "div_audio_slice_and_text": true,
    "embedding": true
  },
  "understanding": {
    "need_video_summary": true,
    "need_image_caption": true,
    "understanding": true
  }
}
```

---

## EventBus Topic 流转汇总

| 阶段 | Topic | 生产者 | 消费者 |
|------|-------|--------|--------|
| 1 | `tiktok.live.multi_guest.generate_summary` | understand_api | understand_consumer |
| 2 | `tiktok.webcast.linkmic.llm.data_grab` | understand_consumer | data_grab |
| 3 | `tiktok.webcast.linkmic.llm.understanding` | data_grab | understanding |
| 4 | `tiktok.webcast.linkmic.llm.result` | understanding | understand_consumer |

---

## IndicatorType 类型说明

| 类型 | 说明 | 选择逻辑 |
|------|------|----------|
| `PCU` | 峰值并发用户数（默认） | 选取连麦期间PCU峰值时刻 |
| `Diamonds` | 钻石收益 | 选取连麦期间钻石峰值时刻 |
| `SendGiftUV` | 送礼用户数 | 选取连麦期间送礼峰值时刻 |
| `FollowUV` | 关注用户数 | 选取连麦期间关注峰值时刻 |
| `CommentUV` | 评论用户数 | 选取连麦期间评论峰值时刻 |
| `Custom{start}-{end}` | 自定义时间区间 | 直接使用指定时间范围 |

---

## 处理模式对比

### 片段理解模式 (type == "")

- 关注指标峰值时刻前后 2 分钟
- 需要实时采集数据或使用预准备素材
- 输出到 `data_grab` 或 `understanding` Topic

### 整场理解模式 (type == "understand")

- 对整场直播进行全面内容理解
- 使用 TNS 音频文本作为主要素材
- 输出到 `data_grab_full` 或 `understanding_full` Topic

---

## 数据库表

### multi_guest_room_fragment_material

存储片段级别的预准备素材，按 `room_id` + `indicator_type` 唯一索引。

**主要字段**:
- 视频/音频资源: `mp4_uris`, `m4a_uris`, `jpeg_uris`
- ASR 文本: `confluence_whisper_texts`, `diversion_whisper_texts`
- 评论: `comments`
- Embedding: `title_sticker_embedding`, `asr_embedding`, `image_embedding`
- 分类结果: `llm_category`, `pseudo_manual_category`, `strategy_category`

---

## 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| RoomID 为空 | 直接返回，不处理 |
| 房间信息查询失败 | 记录日志，发送飞书通知 |
| 房间超过30天 | 记录日志，发送飞书通知 |
| 无连麦记录 | 记录日志，发送飞书通知 |
| 无指标数据 | 记录日志，发送飞书通知 |

---

*文档更新时间: 2026-03-06*
