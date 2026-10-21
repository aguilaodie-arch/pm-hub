# -*- coding: utf-8 -*-
"""migrate_v2.py — 把 data/app.db 从旧模型迁移到 Spec 对齐的新模型（Phase 1）。

用法：
    .venv/Scripts/python migrate_v2.py                 # 默认迁移 data/app.db
    .venv/Scripts/python migrate_v2.py --db 路径.db    # 迁移指定库（如临时副本）

特性：
- 运行开头先备份源库为 <db>.bak-YYYYMMDD-HHMMSS
- 新列用 ALTER TABLE ADD COLUMN，新表用 Base.metadata.create_all
- 幂等：重复执行不报错、不重复迁移
"""
import argparse
import os
import shutil
import sys
from collections import Counter
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import create_engine

from app.config import settings
from app.database import Base
from app import models  # noqa: F401  确保所有表注册到 metadata

# ---- 新列定义：表 -> [(列名, DDL 类型)] ----
NEW_COLUMNS = {
    "users": [
        ("active", "BOOLEAN DEFAULT 1"),
    ],
    "sprints": [
        ("summary", "TEXT"),
        ("kb_doc_id", "VARCHAR(128)"),
        ("archived_by", "INTEGER REFERENCES users(id)"),
    ],
    "publishes": [
        ("entry_path", "VARCHAR(256)"),
        ("file_count", "INTEGER DEFAULT 0"),
        ("total_size", "INTEGER DEFAULT 0"),
        ("updated_at", "DATETIME"),
    ],
    "requirements": [
        ("req_no", "VARCHAR(32)"),
        ("pm_id", "INTEGER REFERENCES users(id)"),
        ("requester", "VARCHAR(128)"),
        ("description", "TEXT"),
        ("planned_online_date", "VARCHAR(16)"),
        ("actual_online_date", "VARCHAR(16)"),
    ],
}

REQ_STATUS_MAP = {
    "clarifying": "待澄清",
    "planned": "待设计",
    "designing": "设计中",
    "review": "待串讲",
    "developing": "研发中",
    "released": "已上线",
    "closed": "已上线",
}
REQ_STATUS_NEW = {"待澄清", "待设计", "设计中", "待串讲", "研发中", "已上线"}
SPRINT_STATUS_MAP = {"active": "进行中", "archived": "已归档"}
SPRINT_STATUS_NEW = {"进行中", "已归档"}
PRIORITY_VALID = {"P0", "P1", "P2"}


def backup_db(db_path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{db_path}.bak-{stamp}"
    shutil.copy2(db_path, bak)
    print(f"[备份] {db_path} -> {bak}")
    return bak


def add_new_columns(conn):
    added = []
    for table, cols in NEW_COLUMNS.items():
        existing = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
        if not existing:
            print(f"[警告] 表 {table} 不存在，跳过加列")
            continue
        for name, ddl in cols:
            if name in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            added.append(f"{table}.{name}")
    print(f"[加列] 新增 {len(added)} 列" + (f"：{', '.join(added)}" if added else "（全部已存在，跳过）"))


def migrate_user_roles(conn):
    n = conn.exec_driver_sql("UPDATE users SET role='pm' WHERE role='member'").rowcount
    print(f"[角色] member→pm 迁移 {n} 条")
    rows = conn.exec_driver_sql("SELECT role, COUNT(*) FROM users GROUP BY role").fetchall()
    for role, cnt in rows:
        print(f"       role={role}: {cnt}")


def migrate_requirement_status(conn):
    migrated = Counter()
    rows = conn.exec_driver_sql("SELECT id, status FROM requirements").fetchall()
    for rid, status in rows:
        s = (status or "").strip()
        if s in REQ_STATUS_NEW:
            continue  # 已是新枚举，幂等跳过
        new = REQ_STATUS_MAP.get(s)
        if new is None:
            print(f"[警告] requirements.id={rid} 未知状态 {status!r}，置为 待澄清")
            new = "待澄清"
        conn.exec_driver_sql("UPDATE requirements SET status=? WHERE id=?", (new, rid))
        migrated[f"{s or '(空)'}→{new}"] += 1
    total = sum(migrated.values())
    print(f"[需求状态] 迁移 {total} 条" + (f"：{dict(migrated)}" if total else "（全部已是新枚举）"))


def migrate_requirement_priority(conn):
    n_p3 = conn.exec_driver_sql("UPDATE requirements SET priority='P2' WHERE priority='P3'").rowcount
    rows = conn.exec_driver_sql(
        "SELECT id, priority FROM requirements WHERE priority IS NULL OR priority NOT IN ('P0','P1','P2')"
    ).fetchall()
    for rid, p in rows:
        print(f"[警告] requirements.id={rid} 未知优先级 {p!r}，置为 P2")
        conn.exec_driver_sql("UPDATE requirements SET priority='P2' WHERE id=?", (rid,))
    print(f"[优先级] P3→P2 归并 {n_p3} 条，未知值修正 {len(rows)} 条")


def backfill_req_no(conn):
    rows = conn.exec_driver_sql(
        "SELECT id, created_at FROM requirements "
        "WHERE req_no IS NULL OR req_no='' ORDER BY created_at, id"
    ).fetchall()
    seq = Counter()
    n = 0
    for rid, created_at in rows:
        day = str(created_at)[:10]  # 库内原值（UTC 字符串/datetime）取日期
        try:
            datetime.strptime(day, "%Y-%m-%d")
            yymmdd = day[2:4] + day[5:7] + day[8:10]
        except Exception:
            print(f"[警告] requirements.id={rid} created_at 无法解析：{created_at!r}，跳过 req_no 回填")
            continue
        seq[day] += 1
        req_no = f"RQ{yymmdd}{seq[day]:04d}"
        conn.exec_driver_sql("UPDATE requirements SET req_no=? WHERE id=?", (req_no, rid))
        n += 1
    print(f"[req_no] 回填 {n} 条" + ("" if rows else "（全部已有值，跳过）"))


def migrate_owner_to_pm(conn):
    users = conn.exec_driver_sql("SELECT id, username, display_name FROM users").fetchall()
    by_name = {}
    for uid, username, display_name in users:
        for key in (display_name, username):
            if key:
                by_name.setdefault(key.strip(), uid)
    rows = conn.exec_driver_sql(
        "SELECT id, owner FROM requirements "
        "WHERE pm_id IS NULL AND owner IS NOT NULL AND TRIM(owner) != ''"
    ).fetchall()
    matched = 0
    for rid, owner in rows:
        uid = by_name.get(owner.strip())
        if uid is None:
            print(f"[警告] requirements.id={rid} 产品经理 {owner!r} 未匹配到用户，pm_id 保留 NULL")
            continue
        conn.exec_driver_sql("UPDATE requirements SET pm_id=? WHERE id=?", (uid, rid))
        matched += 1
    print(f"[pm_id] owner→pm_id 匹配 {matched} 条，未匹配 {len(rows) - matched} 条")


def migrate_sprints(conn):
    migrated = Counter()
    rows = conn.exec_driver_sql("SELECT id, status FROM sprints").fetchall()
    for sid, status in rows:
        s = (status or "").strip()
        if s in SPRINT_STATUS_NEW:
            continue
        new = SPRINT_STATUS_MAP.get(s)
        if new is None:
            print(f"[警告] sprints.id={sid} 未知状态 {status!r}，保持不变")
            continue
        conn.exec_driver_sql("UPDATE sprints SET status=? WHERE id=?", (new, sid))
        migrated[f"{s or '(空)'}→{new}"] += 1
    total = sum(migrated.values())
    print(f"[版本状态] 迁移 {total} 条" + (f"：{dict(migrated)}" if total else "（全部已是新枚举）"))

    # reports → sprints.summary（多条取最新一条；已有 summary 不覆盖，保证幂等）
    reports = conn.exec_driver_sql(
        "SELECT sprint_id, content, created_at FROM reports ORDER BY created_at, id"
    ).fetchall()
    latest = {}
    for sprint_id, content, _ in reports:
        latest[sprint_id] = content
    n = 0
    for sprint_id, content in latest.items():
        cur = conn.exec_driver_sql(
            "UPDATE sprints SET summary=? WHERE id=? AND (summary IS NULL OR summary='')",
            (content, sprint_id),
        )
        n += cur.rowcount
    print(f"[归档摘要] reports→sprints.summary 迁入 {n} 个版本（reports 共 {len(reports)} 条）")


def migrate_design_messages(conn):
    req_ids = [
        r[0]
        for r in conn.exec_driver_sql(
            "SELECT DISTINCT requirement_id FROM design_messages ORDER BY requirement_id"
        )
    ]
    conv_count = msg_count = skipped = 0
    for rid in req_ids:
        exists = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM conversations WHERE requirement_id=?", (rid,)
        ).scalar()
        if exists:
            skipped += 1
            continue  # 幂等：该需求已有 conversation
        req = conn.exec_driver_sql(
            "SELECT title, creator_id, created_at FROM requirements WHERE id=?", (rid,)
        ).fetchone()
        if req is None:
            print(f"[警告] design_messages 引用了不存在的 requirement id={rid}，跳过")
            continue
        title, creator_id, req_created = req
        msgs = conn.exec_driver_sql(
            "SELECT role, skill, content, created_at FROM design_messages "
            "WHERE requirement_id=? ORDER BY created_at, id",
            (rid,),
        ).fetchall()
        first_at = msgs[0][3] if msgs else req_created
        last_at = msgs[-1][3] if msgs else req_created
        cur = conn.exec_driver_sql(
            "INSERT INTO conversations (requirement_id, title, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?)",
            (rid, title, creator_id, first_at, last_at),
        )
        conv_id = cur.lastrowid
        for role, skill, content, created_at in msgs:
            text = content or ""
            if skill and skill.strip():
                text = f"> 技能：{skill.strip()}\n{text}"
            author_id = creator_id if role == "user" else None
            conn.exec_driver_sql(
                "INSERT INTO messages (conversation_id, role, content, author_id, created_at) "
                "VALUES (?,?,?,?,?)",
                (conv_id, role, text, author_id, created_at),
            )
            msg_count += 1
        conv_count += 1
    print(f"[预设计对话] 新建 conversation {conv_count} 条、message {msg_count} 条；跳过已有 {skipped} 个需求")


def _detect_entry(root, html_files):
    """入口探测：index.html → start.html → 目录递归下唯一 .html → NULL。"""
    top = {f.lower() for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))}
    if "index.html" in top:
        return "index.html"
    if "start.html" in top:
        return "start.html"
    if len(html_files) == 1:
        return html_files[0]
    return None


def backfill_publishes(conn):
    rows = conn.exec_driver_sql(
        "SELECT id, dir_path, created_at FROM publishes WHERE updated_at IS NULL ORDER BY id"
    ).fetchall()
    n = 0
    for pid, dir_path, created_at in rows:
        root = os.path.join(settings.publish_root, dir_path or "")
        if not os.path.isdir(root):
            print(f"[警告] publishes.id={pid} 目录不存在：{root}，跳过回填")
            continue
        file_count = 0
        total_size = 0
        html_files = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                file_count += 1
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass
                if fn.lower().endswith(".html"):
                    rel = os.path.relpath(fp, root).replace(os.sep, "/")
                    html_files.append(rel)
        entry = _detect_entry(root, html_files)
        conn.exec_driver_sql(
            "UPDATE publishes SET entry_path=?, file_count=?, total_size=?, updated_at=? WHERE id=?",
            (entry, file_count, total_size, created_at, pid),
        )
        n += 1
        print(f"       publishes.id={pid}: entry={entry!r} files={file_count} size={total_size}")
    print(f"[原型回填] 回填 {n} 条，目录缺失跳过 {len(rows) - n} 条")


def print_report(conn):
    print("\n===== 迁移报告 =====")
    print("角色分布：", dict(conn.exec_driver_sql("SELECT role, COUNT(*) FROM users GROUP BY role").fetchall()))
    print("需求状态分布：", dict(conn.exec_driver_sql("SELECT status, COUNT(*) FROM requirements GROUP BY status").fetchall()))
    print("需求优先级分布：", dict(conn.exec_driver_sql("SELECT priority, COUNT(*) FROM requirements GROUP BY priority").fetchall()))
    print("req_no 已填：", conn.exec_driver_sql("SELECT COUNT(*) FROM requirements WHERE req_no IS NOT NULL AND req_no!=''").scalar(),
          "/", conn.exec_driver_sql("SELECT COUNT(*) FROM requirements").scalar())
    print("pm_id 已匹配：", conn.exec_driver_sql("SELECT COUNT(*) FROM requirements WHERE pm_id IS NOT NULL").scalar())
    print("版本状态分布：", dict(conn.exec_driver_sql("SELECT status, COUNT(*) FROM sprints GROUP BY status").fetchall()))
    print("版本摘要已填：", conn.exec_driver_sql("SELECT COUNT(*) FROM sprints WHERE summary IS NOT NULL AND summary!=''").scalar())
    print("conversations：", conn.exec_driver_sql("SELECT COUNT(*) FROM conversations").scalar())
    print("messages：", conn.exec_driver_sql("SELECT COUNT(*) FROM messages").scalar())
    print("原型已回填：", conn.exec_driver_sql("SELECT COUNT(*) FROM publishes WHERE updated_at IS NOT NULL").scalar(),
          "/", conn.exec_driver_sql("SELECT COUNT(*) FROM publishes").scalar())


def main():
    ap = argparse.ArgumentParser(description="迁移 app.db 到 Spec 对齐的新模型（幂等，可重复执行）")
    ap.add_argument("--db", default=os.path.join("data", "app.db"), help="数据库路径，默认 data/app.db")
    args = ap.parse_args()
    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"[错误] 数据库不存在：{db_path}")
        sys.exit(1)

    backup_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        add_new_columns(conn)
        Base.metadata.create_all(bind=engine)  # 新表：conversations / messages / qa_logs
        migrate_user_roles(conn)
        migrate_requirement_status(conn)
        migrate_requirement_priority(conn)
        backfill_req_no(conn)
        migrate_owner_to_pm(conn)
        migrate_sprints(conn)
        migrate_design_messages(conn)
        backfill_publishes(conn)
        print_report(conn)
    print("\n迁移完成。")


if __name__ == "__main__":
    main()
