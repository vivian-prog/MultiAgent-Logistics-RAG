# API 接口文档

## 1. 入口函数

### 1.1 main()

**文件**: `server.go`

**功能**: 服务主入口，创建EventBus消费者并启动服务

**流程**:
1. 加载EventBus消费者配置
2. 创建多事件消费者
3. 执行初始化
4. 启动消费者

---

### 1.2 Init()

**文件**: `server.go`

**功能**: 服务初始化

**初始化内容**:
| 步骤 | 函数 | 说明 |
|------|------|------|
| 1 | `tcc.InitTcc()` | 初始化配置中心客户端 |
| 2 | `services.InitRedis()` | 初始化Redis客户端 |
| 3 | `services.InitTQSClient()` | 初始化TQS客户端 |
| 4 | `services.InitL3CenterIDF()` | 从Hive加载IDF表 |
| 5 | 启动后台协程 | 每小时刷新IDF表 |
| 6 | `services.InitEventbus()` | 初始化输出EventBus生产者 |

---

### 1.3 EventHandler()

**文件**: `handler.go`

**签名**:
```go
func EventHandler(ctx context.Context, event *eventbus.ConsumerEvent) error
```

**功能**: EventBus事件处理入口，根据事件类型路由到对应处理器

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| event | *eventbus.ConsumerEvent | EventBus事件 |

**返回**: `error` - 处理错误

**事件路由**:
| 事件名 | 处理函数 |
|--------|----------|
| `tiktok.live.llm.voice_txt` | `handler.HandleSlice1Min` |

---

## 2. Handler 层

### 2.1 HandleSlice1Min()

**文件**: `handler/slice_1min.go`

**签名**:
```go
func HandleSlice1Min(ctx context.Context, event *eventbus.ConsumerEvent) error
```

**功能**: 处理1分钟ASR切片事件，提取兴趣标签

**处理流程**:

```
1. 解析事件消息 → getProcessSlice1MinInfo()
2. 获取房间信息 → services.GetRoomData()
3. 判断多连麦房间 → roomSdkInfo.WithLinkMic
4. 时间窗口校验 → utils.IsCongruences()
5. 获取ASR数据 → services.GetArchData2()
6. 分词处理 → tikcast_multi_guest_interest.RawCall.GetTokenization()
7. 分钟级去重
8. 获取L3标签映射 → services.GetL3Center()
9. 计算TF-IDF
10. 排序取Top5
11. 发送结果 → services.SendRoomFeature()
12. 发送日志 → services.SendL3CenterLog()
```

**返回**: `error` - 处理错误

---

### 2.2 getProcessSlice1MinInfo()

**文件**: `handler/slice_1min.go`

**签名**:
```go
func getProcessSlice1MinInfo(ctx context.Context, event *eventbus.ConsumerEvent) (*model.ProcessSlice1MinInfo, error)
```

**功能**: 解析EventBus事件消息

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| event | *eventbus.ConsumerEvent | EventBus事件 |

**返回**:
| 类型 | 说明 |
|------|------|
| `*model.ProcessSlice1MinInfo` | 解析后的处理信息 |
| `error` | 解析错误 |

---

### 2.3 FormatDate()

**文件**: `handler/slice_1min.go`

**签名**:
```go
func FormatDate(ts int64) string
```

**功能**: 将Unix时间戳格式化为UTC日期字符串

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ts | int64 | Unix时间戳（秒） |

**返回**: `string` - 格式化的日期 (yyyyMMdd)

---

## 3. Services 层

### 3.1 Room Service

#### GetRoomData()

**文件**: `services/room.go`

**签名**:
```go
func GetRoomData(ctx context.Context, roomID int64, getRegion bool) (*RoomSdkInfo, error)
```

**功能**: 获取直播间详细信息

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| roomID | int64 | 直播间ID |
| getRegion | bool | 是否获取区域信息 |

**返回**:
| 类型 | 说明 |
|------|------|
| `*RoomSdkInfo` | 房间信息 |
| `error` | 查询错误 |

**RoomSdkInfo 结构**:
```go
type RoomSdkInfo struct {
    RoomID      int64   // 直播间ID
    AnchorID    int64   // 主播ID
    IdcRegion   string  // IDC区域
    CreateTime  int64   // 创建时间
    FinishTime  int64   // 结束时间
    WithLinkMic bool    // 是否开启连麦
    Title       string  // 直播间标题
    Country     string  // 国家
    Region      string  // 区域
    Lang        string  // 语言
}
```

---

### 3.2 Arch Service

#### GetArchData2()

**文件**: `services/arch.go`

**签名**:
```go
func GetArchData2(ctx context.Context, roomID int64, startTimeMS int64, endTimeMS int64, idc string) (materialAudios []*model.MaterialAudio, err error)
```

**功能**: 从LLM Room Serving服务获取ASR数据

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| roomID | int64 | 直播间ID |
| startTimeMS | int64 | 开始时间（毫秒） |
| endTimeMS | int64 | 结束时间（毫秒） |
| idc | string | 数据中心 |

**返回**:
| 类型 | 说明 |
|------|------|
| `[]*model.MaterialAudio` | ASR音频数据列表 |
| `error` | 查询错误 |

---

#### GetArchData()

**文件**: `services/arch.go`

**签名**:
```go
func GetArchData(ctx context.Context, roomID int64, startTime int64, endTime int64, idc string) (materialAudios []*model.MaterialAudio, err error)
```

**功能**: 从RAG Server获取ASR数据（旧版本，分页查询）

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| roomID | int64 | 直播间ID |
| startTime | int64 | 开始时间（秒） |
| endTime | int64 | 结束时间（秒） |
| idc | string | 数据中心 |

---

### 3.3 Redis Service

#### InitRedis()

**文件**: `services/redis.go`

**签名**:
```go
func InitRedis()
```

**功能**: 初始化Redis客户端连接

---

#### GetL3Center()

**文件**: `services/redis.go`

**签名**:
```go
func GetL3Center(ctx context.Context, keywords []string) (map[string]string, error)
```

**功能**: 批量查询关键词到L3兴趣标签的映射

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| keywords | []string | 关键词列表 |

**返回**:
| 类型 | 说明 |
|------|------|
| `map[string]string` | 关键词→L3标签映射 |
| `error` | 查询错误 |

**实现说明**: 将关键词分批（每批50个），并发查询Redis MGet

---

### 3.4 TQS Service

#### InitTQSClient()

**文件**: `services/tqs.go`

**签名**:
```go
func InitTQSClient()
```

**功能**: 初始化TQS客户端

---

#### InitL3CenterIDF()

**文件**: `services/tqs.go`

**签名**:
```go
func InitL3CenterIDF(ctx context.Context)
```

**功能**: 初始化加载IDF表

---

#### RetrieveL3CenterIDF()

**文件**: `services/tqs.go`

**签名**:
```go
func RetrieveL3CenterIDF(ctx context.Context) (map[string]float64, error)
```

**功能**: 从Hive查询IDF表数据

**返回**:
| 类型 | 说明 |
|------|------|
| `map[string]float64` | L3标签→IDF值映射 |
| `error` | 查询错误 |

---

#### GetL3CenterIDF()

**文件**: `services/tqs.go`

**签名**:
```go
func GetL3CenterIDF(ctx context.Context) map[string]float64
```

**功能**: 获取当前IDF表

---

#### RefreshL3CenterIDF()

**文件**: `services/tqs.go`

**签名**:
```go
func RefreshL3CenterIDF(ctx context.Context)
```

**功能**: 刷新IDF表（后台定时调用）

---

### 3.5 EventBus Service

#### InitEventbus()

**文件**: `services/eventbus.go`

**签名**:
```go
func InitEventbus()
```

**功能**: 初始化输出EventBus生产者

---

#### SendRoomFeature()

**文件**: `services/eventbus.go`

**签名**:
```go
func SendRoomFeature(ctx context.Context, msgModel *model.SyncFeatureInfo) error
```

**功能**: 发送兴趣标签特征到EventBus

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| msgModel | *model.SyncFeatureInfo | 特征消息 |

**返回**: `error` - 发送错误

---

#### SendL3CenterLog()

**文件**: `services/eventbus.go`

**签名**:
```go
func SendL3CenterLog(ctx context.Context, msgModel *model.InterestL3CenterLogInfo) error
```

**功能**: 发送L3标签日志到EventBus

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| ctx | context.Context | 上下文 |
| msgModel | *model.InterestL3CenterLogInfo | 日志消息 |

**返回**: `error` - 发送错误

---

## 4. Utils 工具函数

### 4.1 时间处理

#### UTCTimeFormat2TimeUnix()

**文件**: `utils/time.go`

**签名**:
```go
func UTCTimeFormat2TimeUnix(formatTime string) (int64, error)
```

**功能**: 将UTC时间字符串转换为Unix时间戳

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| formatTime | string | UTC时间字符串 (2006-01-02 15:04:05) |

**返回**:
| 类型 | 说明 |
|------|------|
| int64 | Unix时间戳（秒） |
| error | 解析错误 |

---

#### IsCongruences()

**文件**: `utils/time.go`

**签名**:
```go
func IsCongruences(unixTime1, unixTime2 int64, intervalMinutes int) bool
```

**功能**: 判断两个时间戳的分钟数是否对interval取模相等

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| unixTime1 | int64 | 时间戳1 |
| unixTime2 | int64 | 时间戳2 |
| intervalMinutes | int | 间隔分钟数 |

**返回**: `bool` - 是否同余

---

#### IsTimeOverlap()

**文件**: `utils/time.go`

**签名**:
```go
func IsTimeOverlap(startTime1, endTime1, startTime2, endTime2 int64) bool
```

**功能**: 判断两个时间区间是否有重叠

**返回**: `bool` - 是否重叠

---

### 4.2 并发处理

#### Go()

**文件**: `utils/goroutine.go`

**签名**:
```go
func Go(ctx context.Context, f func())
```

**功能**: 启动一个带recover的协程

---

#### PoolGoWithWG()

**文件**: `utils/goroutine.go`

**签名**:
```go
func PoolGoWithWG(ctx context.Context, wg *sync.WaitGroup, f func())
```

**功能**: 使用协程池执行任务，支持WaitGroup

---

### 4.3 监控指标

#### MaterialThroughputMetric()

**文件**: `utils/metrics.go`

**签名**:
```go
func MaterialThroughputMetric(ctx context.Context, idcRegion string, missAudio int)
```

**功能**: 上报ASR数据获取指标

---

#### EmitL3CenterMetric()

**文件**: `utils/metrics.go`

**签名**:
```go
func EmitL3CenterMetric(ctx context.Context, null int)
```

**功能**: 上报TF-IDF结果指标

---

### 4.4 JSON工具

#### ToJSON()

**文件**: `utils/json.go`

**签名**:
```go
func ToJSON(req interface{}) string
```

**功能**: 将对象序列化为JSON字符串

---

## 5. TCC 配置

### 5.1 InitTcc()

**文件**: `tcc/tcc.go`

**签名**:
```go
func InitTcc()
```

**功能**: 初始化TCC配置中心客户端

---

### 5.2 GetTimeRangeConfig()

**文件**: `tcc/tcc.go`

**签名**:
```go
func GetTimeRangeConfig(ctx context.Context) *TimeRangeConfig
```

**功能**: 获取时间范围配置

**返回**: `*TimeRangeConfig` 配置结构

```go
type TimeRangeConfig struct {
    IntervalMinutes  int  // 处理间隔（分钟）
    TimeRangeMinutes int  // 时间窗口范围（分钟）
}
```

---

## 6. 数据模型

### 6.1 输入模型

| 模型 | 文件 | 说明 |
|------|------|------|
| SliceMinInfo | model/eventbus.go | ASR事件消息 |
| ProcessSlice1MinInfo | model/eventbus.go | 解析后的处理信息 |

### 6.2 中间模型

| 模型 | 文件 | 说明 |
|------|------|------|
| MaterialAudio | model/material.go | ASR音频数据 |
| L3CenterTFIDF | model/material.go | TF-IDF计算结果 |
| AsrLiveMgHotWordsIDF | model/hive.go | Hive IDF表记录 |

### 6.3 输出模型

| 模型 | 文件 | 说明 |
|------|------|------|
| InterestL3CenterFeature | model/eventbus.go | 兴趣标签特征 |
| SyncFeatureInfo | model/eventbus.go | 同步特征消息 |
| InterestL3CenterLogInfo | model/eventbus.go | L3标签日志 |
