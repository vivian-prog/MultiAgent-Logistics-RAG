# multi_guest_interest_consumer 项目文档

## 1. 项目概述

### 1.1 项目目的

`multi_guest_interest_consumer` 是一个消费ASR（自动语音识别）事件的服务，主要功能是将直播间语音识别结果与兴趣标签进行关联。通过对直播间语音内容的分析，提取出兴趣标签（L3 Center），用于用户兴趣推荐和内容理解。

### 1.2 核心功能

- 消费ASR语音识别事件
- 对多连麦直播间进行兴趣标签提取
- 使用TF-IDF算法计算兴趣标签权重
- 输出Top5兴趣标签供下游消费

---

## 2. 项目结构

```
multi_guest_interest_consumer/
├── server.go              # 主入口，启动EventBus消费者
├── handler.go             # 事件处理器路由
├── handler/
│   └── slice_1min.go      # 核心业务处理逻辑
├── services/
│   ├── arch.go            # 获取ASR归档数据
│   ├── eventbus.go        # EventBus生产者初始化和消息发送
│   ├── redis.go           # Redis客户端和关键词映射查询
│   ├── room.go            # 获取直播间信息
│   └── tqs.go             # 从Hive加载IDF表
├── model/
│   ├── eventbus.go        # EventBus消息模型
│   ├── hive.go            # Hive数据模型
│   └── material.go        # ASR素材和TF-IDF模型
├── tcc/
│   └── tcc.go             # 配置中心客户端
├── utils/
│   ├── goroutine.go       # 协程池和并发工具
│   ├── json.go            # JSON序列化工具
│   ├── metrics.go         # 监控指标上报
│   └── time.go            # 时间处理工具
├── constdef/
│   └── constdef.go        # 常量定义
└── conf/                  # 配置文件目录
```

---

## 3. 代码链路

### 3.1 启动流程

```
main() → eventbus.NewConsumerMultiEvent() → Init() → c.Run()
                                    ↓
                          EventHandler() [事件回调]
```

### 3.2 初始化流程 (Init)

```
Init()
  ├── tcc.InitTcc()                    # 初始化配置中心
  ├── services.InitRedis()             # 初始化Redis客户端
  ├── services.InitTQSClient()         # 初始化TQS客户端（Hive查询）
  ├── services.InitL3CenterIDF()       # 从Hive加载IDF表
  ├── 启动后台协程                      # 每小时刷新IDF表
  └── services.InitEventbus()          # 初始化输出EventBus生产者
```

### 3.3 事件处理流程

```
EventHandler()
  │
  ├── 事件类型判断
  │     └── TikTokLiveLlmVoiceTxt → HandleSlice1Min()
  │
  └── HandleSlice1Min()
        ├── 1. 解析事件消息 (getProcessSlice1MinInfo)
        ├── 2. 获取房间信息 (GetRoomData)
        ├── 3. 判断是否多连麦房间
        ├── 4. 时间窗口校验 (IsCongruences)
        ├── 5. 获取ASR数据 (GetArchData2)
        ├── 6. 调用分词服务 (GetTokenization)
        ├── 7. 关键词分钟级去重
        ├── 8. 获取关键词→L3标签映射 (GetL3Center)
        ├── 9. 计算TF-IDF分数
        ├── 10. 排序取Top5
        ├── 11. 发送兴趣标签 (SendRoomFeature)
        └── 12. 发送日志 (SendL3CenterLog)
```

---

## 4. 主要方法详解

### 4.1 HandleSlice1Min - 核心处理函数

**位置**: `handler/slice_1min.go`

**功能**: 处理1分钟切片的ASR事件，提取兴趣标签

**主要逻辑**:

```go
func HandleSlice1Min(ctx context.Context, event *eventbus.ConsumerEvent) error {
    // 1. 解析事件
    processSlice1MinInfo, err := getProcessSlice1MinInfo(ctx, event)

    // 2. 获取房间信息
    roomSdkInfo, err := services.GetRoomData(ctx, processSlice1MinInfo.RoomID, false)

    // 3. 过滤非多连麦房间
    if !roomSdkInfo.WithLinkMic {
        return nil
    }

    // 4. 时间窗口校验
    if !utils.IsCongruences(roomSdkInfo.CreateTime, processSlice1MinInfo.WindEndUnix, config.IntervalMinutes) {
        return nil
    }

    // 5. 获取ASR数据
    audios, err := services.GetArchData2(ctx, roomID, startTime*1000, endTime*1000, idcRegion)

    // 6. 分词处理
    tokenResp, err := tikcast_multi_guest_interest.RawCall.GetTokenization(ctx, tokenReq)

    // 7. 按分钟去重关键词
    minuteTokenMap := make(map[int64]map[string]bool)

    // 8. 获取关键词→L3标签映射
    keyword2L3Center, _ := services.GetL3Center(ctx, keywords)

    // 9. 计算TF-IDF
    for l3Center, oneIDF := range IDF {
        if freq, ok := l3Center2Freq[l3Center]; ok {
            tfidfRes = append(tfidfRes, &model.L3CenterTFIDF{
                L3Center: l3Center,
                TFIDF:    math.Log(float64(freq)) * oneIDF,
            })
        }
    }

    // 10. 排序取Top5
    sort.Slice(tfidfRes, func(i, j int) bool { return tfidfRes[i].TFIDF > tfidfRes[j].TFIDF })

    // 11. 发送结果
    services.SendRoomFeature(ctx, f)
    services.SendL3CenterLog(ctx, msg)
}
```

### 4.2 GetArchData2 - 获取ASR数据

**位置**: `services/arch.go`

**功能**: 从 tikcast_llm_room_serving 服务获取时间范围内的ASR数据

**参数**:
- `roomID`: 直播间ID
- `startTimeMS`: 开始时间（毫秒）
- `endTimeMS`: 结束时间（毫秒）
- `idc`: 数据中心

**返回**: `[]*model.MaterialAudio` ASR音频文本列表

### 4.3 GetL3Center - 获取兴趣标签映射

**位置**: `services/redis.go`

**功能**: 从Redis批量查询关键词到L3兴趣标签的映射

**实现**: 将关键词分批（每批50个），并发查询Redis MGet

### 4.4 TF-IDF计算

**算法说明**:
- **TF (词频)**: 关键词在时间窗口内出现的分钟数（去重后）
- **IDF (逆文档频率)**: 从Hive表预加载的全局IDF值
- **TF-IDF**: `log(TF) * IDF`

---

## 5. 数据模型

### 5.1 输入模型

```go
// SliceMinInfo - ASR事件消息结构
type SliceMinInfo struct {
    Flag      string `json:"_flag"`
    VRegion   string `json:"v_region"`
    RoomID    int64  `json:"room_id"`
    WindStart string `json:"wind_start"`   // 时间窗口开始
    WindEnd   string `json:"wind_end"`     // 时间窗口结束
    RoomInfo  string `json:"room_info"`
    AudioInfo string `json:"audio_info"`
    ImageInfo string `json:"image_info"`
    MsgInfo   string `json:"msg_info"`
}
```

### 5.2 中间模型

```go
// MaterialAudio - ASR音频数据
type MaterialAudio struct {
    UserID    int64   // 用户ID
    Uri       string  // 音频URI
    Text      string  // ASR识别文本
    StartTime int64   // 开始时间（毫秒）
    EndTime   int64   // 结束时间（毫秒）
}

// L3CenterTFIDF - TF-IDF计算结果
type L3CenterTFIDF struct {
    L3Center string  // 兴趣标签
    TFIDF    float64 // TF-IDF分数
    TF       int     // 词频
    IDF      float64 // 逆文档频率
}
```

### 5.3 输出模型

```go
// InterestL3CenterFeature - 兴趣标签特征
type InterestL3CenterFeature struct {
    RoomID        int64    `json:"room_id"`
    AnchorID      int64    `json:"anchor_id"`
    WindStartUnix int64    `json:"wind_start_unix"`
    WindEndUnix   int64    `json:"wind_end_unix"`
    L3Center      []string `json:"l3_center"`       // Top5兴趣标签
}

// InterestL3CenterLogInfo - 日志记录
type InterestL3CenterLogInfo struct {
    RoomID           int64  `json:"room_id"`
    AnchorID         int64  `json:"anchor_id"`
    WindStartUnix    int64  `json:"wind_start_unix"`
    WindEndUnix      int64  `json:"wind_end_unix"`
    L3Center         string `json:"l3_center"`          // TF-IDF结果JSON
    ASRText          string `json:"asr_text"`           // ASR文本JSON
    WordSegmentation string `json:"word_segmentation"`  // 分词结果JSON
    Date             string `json:"date"`               // 日期
}
```

---

## 6. 数据流动图

### 6.1 整体数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据流动全景图                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌─────────────────────────┐     ┌──────────────────────┐
│   EventBus   │────▶│  multi_guest_interest_  │────▶│      EventBus        │
│  (ASR事件)   │     │       consumer          │     │  (兴趣标签/日志)     │
└──────────────┘     └─────────────────────────┘     └──────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Room SDK    │     │ LLM Room     │     │    Redis     │
│  (房间信息)  │     │ Serving      │     │ (关键词映射) │
│              │     │ (ASR数据)    │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
                     ┌──────────────┐
                     │ 分词服务     │
                     │ (Tokenization)│
                     └──────────────┘
```

### 6.2 核心处理流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HandleSlice1Min 处理流程                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 解析事件    │───▶│ 获取房间    │───▶│ 判断多连麦  │───▶│ 时间校验    │
│ 消息        │    │ 信息        │    │ 房间过滤    │    │             │
└─────────────┘    └─────────────┘    └──────┬──────┘    └─────────────┘
                                             │
                   ┌─────────────────────────┘
                   │
                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 获取ASR     │───▶│ 调用分词    │───▶│ 分钟级      │───▶│ 获取L3      │
│ 数据        │    │ 服务        │    │ 去重        │    │ 标签映射    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                   │
                   ┌───────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 计算TF-IDF  │───▶│ 排序取      │───▶│ 发送兴趣    │───▶│ 发送日志    │
│ 分数        │    │ Top5        │    │ 标签        │    │ 记录        │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 7. 配置说明

### 7.1 TCC配置

**配置Key**: `tikcast.multi_guest.interest_consumer`

**配置项**:

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `interval_minutes` | int | 1 | 处理间隔（分钟） |
| `time_range_minutes` | int | 30 | 时间窗口范围（分钟） |

### 7.2 EventBus配置

| EventBus名称 | 方向 | 说明 |
|-------------|------|------|
| `tiktok.live.llm.voice_txt` | 消费 | ASR事件输入 |
| `tiktok.webcast.multi_guest.sync_feature` | 生产 | 兴趣标签输出 |
| `tiktok.webcast.linkmic.interest_l3center_log` | 生产 | 日志输出 |

---

## 8. 外部依赖

### 8.1 服务依赖

| 服务 | 用途 |
|------|------|
| tikcast_multi_guest_interest | 分词服务 |
| tikcast_llm_room_serving | 获取ASR数据 |
| room_sdk | 获取直播间信息 |
| Redis | 关键词→L3标签映射存储 |
| TQS (Hive) | IDF表数据源 |

### 8.2 存储依赖

| 存储 | Key | 用途 |
|------|-----|------|
| Redis | `toutiao.redis.multi_guest_interest_feature.service.my` | 关键词映射 |
| Hive | `tiktok_linkmic.asr_live_mg_hotwords_idf` | IDF表 |

---

## 9. 监控指标

| 指标名 | 标签 | 说明 |
|--------|------|------|
| `material_throughput` | idc_region, miss_audio | ASR数据获取情况 |
| `l3_center` | null | TF-IDF结果是否为空 |

---

## 10. 关键算法说明

### 10.1 TF-IDF计算

```
TF-IDF = log(TF) × IDF

其中:
- TF: 关键词在时间窗口内出现的分钟数（按分钟去重后的频率）
- IDF: 从Hive表预加载的全局逆文档频率
```

### 10.2 分钟级去重策略

为避免同一分钟内重复出现的关键词对TF计算的干扰，采用分钟级去重：

```go
// 按分钟分组
minuteKey := audioStartTimeSec - (audioStartTimeSec % 60)

// 每分钟内关键词去重
minuteTokenMap[minuteKey][token] = true
```

---

## 11. 部署说明

### 11.1 运行环境

- Go版本: 1.24.2
- 部署方式: Kubernetes

### 11.2 启动命令

```bash
# 编译
go build -o multi_guest_interest_consumer

# 运行
./multi_guest_interest_consumer
```

---

## 12. 注意事项

1. **多连麦过滤**: 仅处理开启连麦功能的直播间
2. **时间窗口校验**: 只处理与直播间创建时间模运算一致的时间切片
3. **IDF表刷新**: 服务启动后每小时自动刷新IDF表
4. **异步日志**: 日志发送采用异步协程，不阻塞主流程
