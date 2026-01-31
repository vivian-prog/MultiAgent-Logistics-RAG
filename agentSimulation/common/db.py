# common/db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session as SyncSession
import urllib.parse

# 加载环境变量（从项目根目录的.env文件）
load_dotenv()

# -------------------------- 基础配置 --------------------------
# 数据库配置（读取.env或默认值）
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "huangw293"),
    "password": os.getenv("DB_PASSWORD", "Huangw293!@#"),
    "database": os.getenv("DB_NAME", "hma_llm"),
    "charset": "utf8mb4",
    "port": int(os.getenv("DB_PORT", 3306))
}

# 密码URL编码（处理#、@等特殊字符）
encoded_password = urllib.parse.quote_plus(DB_CONFIG["password"])

# -------------------------- 异步数据库配置（FastAPI用） --------------------------
# 异步连接URL（适配MySQL异步驱动）
ASYNC_DB_URL = (
    f"mysql+aiomysql://{DB_CONFIG['user']}:{encoded_password}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
)

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DB_URL,
    echo=False,  # 生产环境设为False，调试时设为True（打印SQL）
    pool_size=10,  # 连接池大小
    max_overflow=20,
    pool_recycle=3600,  # 1小时回收连接，避免超时
)

# 异步会话工厂
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后不自动过期对象
    autoflush=False,
    autocommit=False
)

# -------------------------- 同步数据库配置（Celery任务用） --------------------------
# 同步连接URL（适配MySQL同步驱动）
SYNC_DB_URL = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
)

# 创建同步引擎
sync_engine = create_engine(
    SYNC_DB_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)

# 同步会话工厂
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=SyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

# -------------------------- 公共Base类（所有模型继承） --------------------------
Base = declarative_base()

# -------------------------- 依赖注入函数（FastAPI用） --------------------------
async def get_db() -> AsyncSession:
    """
    FastAPI依赖注入：获取异步数据库会话
    使用方式：db: AsyncSession = Depends(get_db)
    """
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

# -------------------------- 同步会话获取函数（Celery任务用） --------------------------
def get_sync_db() -> SyncSession:
    """
    Celery任务用：获取同步数据库会话
    使用方式：db = next(get_sync_db())
    """
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()