# TextRAG - 基于FAISS的文本检索服务

## 概述

本模块实现了基于FAISS向量数据库的文本RAG检索服务，用于消融实验中与GraphRAG进行对比。

## 架构说明

```
TextRAG/
├── faiss_service.py      # FAISS服务主程序
├── faiss_index/          # FAISS索引存储目录
│   ├── text_vectors.index  # 向量索引文件
│   └── text_metadata.json  # 文本元数据
└── README.md             # 说明文档
```

## 与GraphRAG的区别

| 特性 | TextRAG (FAISS) | GraphRAG |
|------|----------------|----------|
| 检索方式 | 向量相似度检索 | 知识图谱检索 |
| 数据结构 | 平面向量索引 | 图结构（实体+关系） |
| 检索粒度 | 文本片段级别 | 实体/社区级别 |
| 上下文构建 | Top-K相似文本 | 相关实体+社区报告 |
| 服务端口 | 8016 | 8015 |
| 模型名称 | faiss-text-search:latest | graphrag-global-search:latest |

## 安装依赖

```bash
pip install faiss-cpu  # 或 pip install faiss-gpu (如有GPU)
pip install openai pandas pydantic fastapi uvicorn
```

## 启动服务

```bash
# 方式1: 直接运行
cd TextRAG
python faiss_service.py

# 方式2: 指定配置
EMBEDDING_API_BASE=http://localhost:8021/v1 \
EMBEDDING_MODEL=Qwen3-Embedding-8B \
TEXTRAG_PORT=8016 \
python faiss_service.py
```

## API接口

### 1. 聊天补全接口 (OpenAI兼容)

```bash
POST http://localhost:8016/v1/chat/completions

{
    "model": "faiss-text-search:latest",
    "messages": [{"role": "user", "content": "查询内容"}],
    "temperature": 0.7
}
```

### 2. 搜索接口

```bash
GET http://localhost:8016/search?query=查询内容&top_k=5
```

### 3. 健康检查

```bash
GET http://localhost:8016/health
```

### 4. 重建索引

```bash
POST http://localhost:8016/rebuild_index
```

## 配置项

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| TEXTRAG_INPUT_DIR | ../GraphRag/inputs/artifacts | 数据源目录 |
| EMBEDDING_API_BASE | http://localhost:8021/v1 | Embedding服务地址 |
| EMBEDDING_API_KEY | ollama | API密钥 |
| EMBEDDING_MODEL | Qwen3-Embedding-8B | Embedding模型 |
| TEXTRAG_PORT | 8016 | 服务端口 |
| TEXTRAG_TOP_K | 5 | 默认返回结果数 |

## 数据来源

TextRAG使用GraphRAG预处理生成的 `create_final_text_units.parquet` 文件作为数据源。该文件包含：

- `id`: 文本单元ID
- `text`: 文本内容
- `document_ids`: 关联文档ID
- `entity_ids`: 关联实体ID
- `relationship_ids`: 关联关系ID

## 在消融实验中使用

消融实验脚本 (`experiments/run_ablation.py`) 已配置为：

- `text_rag` 配置: 使用FAISS文本检索服务 (端口8016)
- `graphrag` 配置: 使用GraphRAG服务 (端口8015)
- `no_rag` 配置: 不使用任何RAG

## 检索流程

```
用户查询
    ↓
生成Query Embedding
    ↓
FAISS向量相似度搜索
    ↓
返回Top-K相似文本片段
    ↓
格式化为上下文
    ↓
返回给LLM进行推理
```
