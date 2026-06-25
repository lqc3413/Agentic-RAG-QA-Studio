"""共享 PostgreSQL 连接池管理器。

所有业务数据管理器（UserManager、AgentMemoryManager 等）
统一从此模块获取同一个同步连接池，避免重复创建连接。
"""
from psycopg_pool import NullConnectionPool
from psycopg.rows import dict_row

import config

_pool: NullConnectionPool | None = None


def get_pool() -> NullConnectionPool:
    """返回全局共享的同步连接池（懒初始化、线程安全）。"""
    global _pool
    if _pool is None:
        _pool = NullConnectionPool(
            conninfo=config.POSTGRES_DSN,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
    return _pool


def close_pool() -> None:
    """关闭全局连接池（用于进程退出前清理）。"""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def clear_all_tables() -> None:
    """清空所有业务相关的表（主要用于单元测试）。"""
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute("TRUNCATE TABLE users, agent_memories, qa_records, sessions, document_metadata RESTART IDENTITY CASCADE")
