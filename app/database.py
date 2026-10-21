import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})


if settings.db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        # WAL：读写互不阻塞，提升多人并发；busy_timeout：写锁冲突时等待而非立刻报错
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def init_db():
    os.makedirs(settings.publish_root, exist_ok=True)
    os.makedirs(settings.chroma_dir, exist_ok=True)
    if settings.db_url.startswith("sqlite:///"):
        db_path = settings.db_url.replace("sqlite:///", "", 1)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """轻量迁移：为已存在的表补充新列。"""
    with engine.begin() as c:
        cols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(requirements)")]
        if cols and "user_story" not in cols:
            c.exec_driver_sql("ALTER TABLE requirements ADD COLUMN user_story TEXT")
        if cols and "jira_sync" not in cols:
            c.exec_driver_sql("ALTER TABLE requirements ADD COLUMN jira_sync TEXT DEFAULT ''")
        if cols and "jira_error" not in cols:
            c.exec_driver_sql("ALTER TABLE requirements ADD COLUMN jira_error TEXT")
        kcols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(knowledge_entries)")]
        if kcols and "publish_ids" not in kcols:
            c.exec_driver_sql("ALTER TABLE knowledge_entries ADD COLUMN publish_ids TEXT DEFAULT ''")
        ucols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(users)")]
        if ucols and "dingtalk_userid" not in ucols:
            c.exec_driver_sql("ALTER TABLE users ADD COLUMN dingtalk_userid TEXT DEFAULT ''")
        qcols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(qa_logs)")]
        if qcols:
            if "summary" not in qcols:
                c.exec_driver_sql("ALTER TABLE qa_logs ADD COLUMN summary TEXT")
            if "push_status" not in qcols:
                c.exec_driver_sql("ALTER TABLE qa_logs ADD COLUMN push_status TEXT DEFAULT ''")
            if "push_error" not in qcols:
                c.exec_driver_sql("ALTER TABLE qa_logs ADD COLUMN push_error TEXT")
        pcols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(publishes)")]
        if pcols and "kind" not in pcols:
            c.exec_driver_sql("ALTER TABLE publishes ADD COLUMN kind TEXT DEFAULT 'prototype'")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
