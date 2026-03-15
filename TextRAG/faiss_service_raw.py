#!/usr/bin/env python
# TextRAG/faiss_service_raw.py
"""
基于FAISS的原始文本RAG服务
使用GraphRag/input目录下的原始txt文件作为知识库语料
"""
import os
import json
import time
import uuid
import logging
import asyncio
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from openai import OpenAI

# FAISS导入
try:
    import faiss
except ImportError:
    raise ImportError("请安装faiss: pip install faiss-cpu 或 pip install faiss-gpu")

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== 配置 =====================
# 原始文本目录
RAW_INPUT_DIR = os.environ.get(
    "RAW_INPUT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "GraphRag", "input")
)

FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index_raw")
FAISS_INDEX_FILE = os.path.join(FAISS_INDEX_DIR, "raw_text_vectors.index")
METADATA_FILE = os.path.join(FAISS_INDEX_DIR, "raw_text_metadata.json")

EMBEDDING_API_BASE = os.environ.get("EMBEDDING_API_BASE", "http://localhost:8021/v1")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "ollama")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "Qwen3-Embedding-8B")

PORT = int(os.environ.get("TEXTRAG_RAW_PORT", "8017"))
TOP_K = int(os.environ.get("TEXTRAG_TOP_K", "5"))

# 全局变量
faiss_index = None
text_metadata = None
embedding_client = None


# ===================== Pydantic模型 =====================
class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Usage


# ===================== Embedding函数 =====================
def get_embedding_client() -> OpenAI:
    global embedding_client
    if embedding_client is None:
        embedding_client = OpenAI(base_url=EMBEDDING_API_BASE, api_key=EMBEDDING_API_KEY)
    return embedding_client


def get_embedding(text: str) -> np.ndarray:
    client = get_embedding_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return np.array(response.data[0].embedding, dtype=np.float32)


def batch_get_embeddings(texts: List[str], max_tokens_per_batch: int = 7000) -> np.ndarray:
    """
    批量获取embedding，基于token数量动态分批以避免超出模型限制
    Args:
        texts: 文本列表
        max_tokens_per_batch: 每批次最大token数（保守估计，留出余量）
    """
    client = get_embedding_client()
    all_embeddings = []

    # 简单的token估算：中文约1.5字符/token，英文约4字符/token
    def estimate_tokens(text: str) -> int:
        # 保守估计：字符数/2
        return max(1, len(text) // 2)

    i = 0
    while i < len(texts):
        batch_texts = []
        current_tokens = 0
        batch_start = i

        # 动态构建批次，确保不超过token限制
        while i < len(texts):
            text_tokens = estimate_tokens(texts[i])
            if current_tokens + text_tokens > max_tokens_per_batch and batch_texts:
                # 当前批次已满，开始新批次
                break
            batch_texts.append(texts[i])
            current_tokens += text_tokens
            i += 1

        # 如果单个文本就超过限制，需要截断
        if len(batch_texts) == 1 and current_tokens > max_tokens_per_batch:
            # 截断到大约max_tokens_per_batch * 2字符
            max_chars = max_tokens_per_batch * 2
            batch_texts[0] = batch_texts[0][:max_chars] + "...[截断]"
            logger.warning(f"文本过长已截断，原估算token数: {current_tokens}")

        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch_texts)
        batch_embeddings = [np.array(item.embedding, dtype=np.float32) for item in response.data]
        all_embeddings.extend(batch_embeddings)
        logger.info(f"已处理 {i}/{len(texts)} 条文本的embedding (批次token数约: {current_tokens})")

    return np.array(all_embeddings, dtype=np.float32)


# ===================== 数据加载函数 =====================
def load_raw_text_files() -> List[Dict[str, Any]]:
    """
    从GraphRag/input目录加载原始txt文件
    将每个文件分割成多个文本块
    """
    if not os.path.exists(RAW_INPUT_DIR):
        raise FileNotFoundError(f"原始文本目录不存在: {RAW_INPUT_DIR}")

    text_units = []
    chunk_id = 0

    # 遍历目录下所有txt文件
    for filename in os.listdir(RAW_INPUT_DIR):
        if not filename.endswith('.txt'):
            continue

        filepath = os.path.join(RAW_INPUT_DIR, filename)
        logger.info(f"加载文件: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 策略1: 按段落分割（双换行符）
            paragraphs = content.split('\n\n')

            for para in paragraphs:
                para = para.strip()
                if len(para) < 50:  # 过滤太短的段落
                    continue

                text_units.append({
                    "id": str(chunk_id),
                    "text": para,
                    "source_file": filename,
                    "chunk_type": "paragraph"
                })
                chunk_id += 1

            # 策略2: 对于表格数据，按行分割
            if '第' in content and '个数据' in content:
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('第') and '个数据' in line:
                        text_units.append({
                            "id": str(chunk_id),
                            "text": line,
                            "source_file": filename,
                            "chunk_type": "data_row"
                        })
                        chunk_id += 1

        except Exception as e:
            logger.error(f"读取文件 {filepath} 失败: {e}")
            continue

    logger.info(f"从原始文本文件加载了 {len(text_units)} 个文本块")
    return text_units


# ===================== FAISS索引管理 =====================
def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    n_vectors, dim = embeddings.shape
    logger.info(f"构建FAISS索引: {n_vectors}个向量, 维度={dim}")
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    logger.info(f"FAISS索引构建完成，共 {index.ntotal} 个向量")
    return index


def save_faiss_index_file(index: faiss.Index, metadata: List[Dict]):
    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_FILE)
    logger.info(f"FAISS索引已保存到: {FAISS_INDEX_FILE}")
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    logger.info(f"元数据已保存到: {METADATA_FILE}")


def load_faiss_index_file() -> Tuple[faiss.Index, List[Dict]]:
    if not os.path.exists(FAISS_INDEX_FILE):
        raise FileNotFoundError(f"FAISS索引文件不存在: {FAISS_INDEX_FILE}")
    index = faiss.read_index(FAISS_INDEX_FILE)
    logger.info(f"FAISS索引已加载，共 {index.ntotal} 个向量")
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    logger.info(f"元数据已加载，共 {len(metadata)} 条记录")
    return index, metadata


def search_similar_texts(query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    global faiss_index, text_metadata
    if faiss_index is None or text_metadata is None:
        raise RuntimeError("FAISS索引未初始化")

    query_embedding = get_embedding(query).reshape(1, -1)
    faiss.normalize_L2(query_embedding)
    scores, indices = faiss_index.search(query_embedding, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if 0 <= idx < len(text_metadata):
            results.append({
                "text": text_metadata[idx]["text"],
                "score": float(score),
                "id": text_metadata[idx]["id"],
                "source_file": text_metadata[idx].get("source_file", "unknown"),
                "chunk_type": text_metadata[idx].get("chunk_type", "unknown")
            })
    return results


# ===================== 初始化函数 =====================
async def initialize_faiss_index(rebuild: bool = False):
    global faiss_index, text_metadata

    if not rebuild and os.path.exists(FAISS_INDEX_FILE) and os.path.exists(METADATA_FILE):
        logger.info("发现已有的FAISS索引，正在加载...")
        faiss_index, text_metadata = load_faiss_index_file()
        return

    logger.info("开始构建FAISS索引（原始文本）...")
    text_units = load_raw_text_files()
    texts = [unit["text"] for unit in text_units]
    logger.info(f"正在为 {len(texts)} 条文本生成embedding...")
    embeddings = batch_get_embeddings(texts)
    faiss_index = build_faiss_index(embeddings)
    text_metadata = text_units
    save_faiss_index_file(faiss_index, text_metadata)
    logger.info("FAISS索引初始化完成")


# ===================== FastAPI应用 =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("正在初始化原始文本TextRAG服务...")
        await initialize_faiss_index(rebuild=False)
        logger.info("原始文本TextRAG服务初始化完成")
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise
    yield
    logger.info("正在关闭原始文本TextRAG服务...")


app = FastAPI(lifespan=lifespan, title="Raw Text RAG FAISS Service")


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if faiss_index is None:
        raise HTTPException(status_code=500, detail="FAISS索引未初始化")

    query = request.messages[-1].content
    logger.info(f"查询文本: {query[:100]}...")

    results = search_similar_texts(query, top_k=TOP_K)

    formatted_response = "# Raw TextRAG检索结果:\n\n"
    for i, result in enumerate(results, 1):
        formatted_response += f"## 相关片段 {i} (相似度: {result['score']:.4f}, 来源: {result['source_file']}):\n"
        formatted_response += f"{result['text']}\n\n"

    logger.info(f"返回 {len(results)} 条相关文本")

    if request.stream:
        async def generate_stream():
            chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
            for line in formatted_response.split('\n'):
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {"content": line + '\n'}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk)}\n"
                await asyncio.sleep(0.1)
            final = {"id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": request.model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(final)}\n"
            yield "data: [DONE]\n"
        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    response = ChatCompletionResponse(
        model=request.model,
        choices=[ChatCompletionResponseChoice(index=0, message=Message(role="assistant", content=formatted_response), finish_reason="stop")],
        usage=Usage(prompt_tokens=len(query.split()), completion_tokens=len(formatted_response.split()), total_tokens=len(query.split()) + len(formatted_response.split()))
    )
    return JSONResponse(content=response.dict())


@app.get("/v1/models")
async def list_models():
    return JSONResponse(content={"object": "list", "data": [{"id": "faiss-raw-text-search:latest", "object": "model", "created": int(time.time()), "owned_by": "faiss-raw-textrag"}]})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "index_size": faiss_index.ntotal if faiss_index else 0, "metadata_count": len(text_metadata) if text_metadata else 0}


@app.post("/rebuild_index")
async def rebuild_index():
    try:
        await initialize_faiss_index(rebuild=True)
        return {"status": "success", "message": "FAISS索引已重建"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_api(query: str, top_k: int = TOP_K):
    results = search_similar_texts(query, top_k=top_k)
    return {"query": query, "results": results}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"在端口 {PORT} 上启动原始文本TextRAG FAISS服务")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
