# 代码逻辑图

## 1. 服务启动流程

```mermaid
flowchart TD
    A[main.go] --> B[创建 Kitex Server]
    B --> C[Init 初始化]
    C --> D[services.InitTos<br/>初始化 TOS 客户端]
    C --> E[handlers.InitCacheRefresher<br/>初始化房间缓存]
    D --> F[启动 Server<br/>svr.Run]
    E --> F

    subgraph InitTos
        D1[读取 TCC 配置] --> D2[初始化 TNS TOS 客户端]
        D2 --> D3[初始化 Self TOS 客户端]
    end

    subgraph InitCacheRefresher
        E1[创建 anycache Fetcher] --> E2[创建异步刷新器]
        E2 --> E3[同步获取一次房间列表]
        E3 --> E4[启动定时刷新]
    end
```

## 2. RPC 接口路由

```mermaid
flowchart LR
    subgraph Client
        C1[调用方]
    end

    subgraph Server[linkmic_understand_svr]
        H[handler.go<br/>LinkmicUnderstandServiceImpl]

        H --> H1[OperateFile]
        H --> H2[GetLeaveCategorySurvey]
        H --> H3[SubmitLeaveCategorySurvey]
        H --> H4[MsetTaskResult_]
        H --> H5[CheckNewModel]
        H --> H6[NotifyModelUpdate]
        H --> H7[UpdateModelServiceCallback]
        H --> H8[GetGameplayTag]
        H --> H9[CheckSelection]
        H --> H10[GetAllSelectedRoom]
    end

    C1 -->|Kitex RPC| H
```

## 3. OperateFile 处理流程

```mermaid
flowchart TD
    A[OperateFile Request] --> B{参数校验}
    B -->|失败| C[返回参数错误]
    B -->|成功| D{特殊标记?<br/>startTime=1&endTime=1}

    D -->|是| E[发送切片标签消息<br/>SendSliceTagMsg]
    D -->|否| F[GetRtcSlice<br/>获取 RTC 切片]

    F --> G[遍历音频单元]
    G --> H[GetTnsTosBody<br/>下载音频]
    H --> I[PutSelfTosBody<br/>上传到自有 TOS]
    I --> J{需要跨区域复制?}
    J -->|是| K[CopySelfTosAudioObj]
    J -->|否| L[下一个音频]
    K --> L
    L --> G

    G -->|遍历完成| M[排序文件名]
    M --> N[返回文件列表]
    E --> N
```

## 4. TCS 审核回调处理流程

```mermaid
flowchart TD
    A[MSetTaskResultReq] --> B{TcsTaskResultHandler}

    B --> C{ProjectId 判断}

    C -->|GoldenCaseReviewQueueID| D[专家审核回调]
    C -->|其他| E[BPO 审核回调]

    subgraph 专家审核流程
        D --> D1[解析审核表单]
        D1 --> D2[提取 GameplayCategory]
        D2 --> D3[验证并排序标签]
        D3 --> D4[构建 ProduceGoldenCaseEvent]
        D4 --> D5[发送 EventBus 消息]
    end

    subgraph BPO审核流程
        E --> E1[遍历 TaskResults]
        E1 --> E2[解析每个审核结果]
        E2 --> E3[提取分类标签]
        E3 --> E4[验证标签有效性]
        E4 --> E5{审核人数 >= 2?}

        E5 -->|否| E6[跳过该任务]
        E5 -->|是| E7[投票统计]
        E7 --> E8[确定最终分类]
        E8 --> E9[更新数据库<br/>UpdateMultiGuestRoomFragmentMaterialByID]
        E9 --> E10{启用 Golden Case Pipeline?}
        E10 -->|是| E11[发送 EventBus 消息]
        E10 -->|否| E12[完成]
        E11 --> E12
    end
```

## 5. CheckNewModel 处理流程

```mermaid
flowchart TD
    A[CheckNewModel Request] --> B[异步执行]

    subgraph 异步处理
        B --> C[CheckHdfsModelToday]
        C --> D{最近7天有新模型?}

        D -->|否| E[返回 未找到新模型]

        D -->|是| F[HdfsFileGet<br/>读取 metrics.json]
        F --> G[解析 Metrics 结构]
        G --> H[填充 matrixSource]
        H --> I[格式化整体准确率]
        I --> J[格式化 VIP 准确率]
        J --> K[格式化各分类准召]
        K --> L[LarkMatrixText<br/>生成混淆矩阵]
        L --> M[拼接完整文本]
        M --> N[LarkMessageSend<br/>发送飞书消息]
    end

    A --> O[立即返回成功]
```

## 6. GetAllSelectedRoom 处理流程

```mermaid
flowchart TD
    A[GetAllSelectedRoom Request] --> B[从缓存获取房间列表]
    B --> C{缓存命中?}

    C -->|是| D[返回缓存数据]
    C -->|否| E[loadAllLinkMicSelectedRoom]

    subgraph 加载房间列表
        E --> F[room.GetAllOnlineRoomsData<br/>获取所有在线房间]
        F --> G[遍历房间数据]
        G --> H[解析 RoomExtra]
        H --> I{是多嘉宾模式?}
        I -->|否| J[跳过]
        I -->|是| K{检查 AB 参数}

        K -->|命中 AB 参数| L[加入列表]
        K -->|未命中| M{检查国家配置}
        M -->|命中国家分流| L
        M -->|未命中| J

        L --> N[下一个房间]
        J --> N
        N --> G
    end

    subgraph 缓存刷新机制
        direction LR
        P[AsyncRefresher] -->|每10秒| Q[检查缓存过期]
        Q -->|过期| R[异步刷新]
        R --> S[更新缓存]
    end

    E --> D
```

## 7. 模型更新流程

```mermaid
flowchart TD
    A[NotifyModelUpdate Request] --> B[异步执行]

    subgraph 异步更新
        B --> C[UpdateModelService]
        C --> D[调用 tikcast_llm_model_guardian<br/>UpdateModelService]
        D --> E{ResultCode}

        E -->|1 需要指定版本| F[带上 ModelVersion 重试]
        E -->|-1 失败| G[记录错误]
        E -->|0 成功| H[完成]

        F --> I{重试结果}
        I -->|成功| H
        I -->|失败| G
    end

    A --> J[立即返回成功]

    K[UpdateModelServiceCallback] --> L[构建飞书消息]
    L --> M{ResultCode}
    M -->|0| N[更新成功]
    M -->|-1| O[更新失败，请重试]
    M -->|其他| P[更新失败]
    N --> Q[LarkMessageSend]
    O --> Q
    P --> Q
```

## 8. Handler 通用模式

```mermaid
classDiagram
    class BaseHandler {
        +ctx context.Context
        +req Request
    }

    class OperateFileHandler {
        +Handle() Response
    }

    class TcsTaskResultHandler {
        +Handle() Response
    }

    class CheckNewModelHandler {
        +Handle() Response
    }

    class GetAllSelectedRoomHandler {
        +Handle() Response
    }

    BaseHandler <|-- OperateFileHandler
    BaseHandler <|-- TcsTaskResultHandler
    BaseHandler <|-- CheckNewModelHandler
    BaseHandler <|-- GetAllSelectedRoomHandler

    class HandlerFactory {
        +NewPreOperateFileHandler(ctx, req)
        +NewPreTcsTaskResultHandler(ctx, req)
        +NewPreCheckNewModelHandler(ctx, req)
        +NewGetAllSelectedRoomHandler(ctx, req)
    }

    HandlerFactory ..> OperateFileHandler : creates
    HandlerFactory ..> TcsTaskResultHandler : creates
    HandlerFactory ..> CheckNewModelHandler : creates
    HandlerFactory ..> GetAllSelectedRoomHandler : creates
```

## 9. 分类标签验证流程

```mermaid
flowchart TD
    A[输入标签列表] --> B[GameplayCategoryLevelTree<br/>.HelpValidateAndSort]

    B --> C{遍历标签}
    C --> D{标签在树中?}
    D -->|是| E[添加到结果]
    D -->|否| F[跳过]

    E --> G{有子树?}
    G -->|是| H[递归验证子标签]
    G -->|否| I[下一个标签]

    H --> I
    F --> I
    I --> C

    C -->|遍历完成| J[返回排序后的有效标签]

    subgraph GameplayCategoryLevelTree
        K["NotMyLanguage"]
        L["Abandon"]
        M["BoxBattle"]
        N["Consulting"]
        O["Debating"]
        P["TalentShow"]
        Q["NoGameplay"]
        R["UnCovered"]
        S["Dating"] --> T["TMO"]
    end
```
