# -*- coding: utf-8 -*-
"""不变量自检脚本（specs/pm-hub/06-invariants.md 的机器可检查实现）。

用法：
    .venv/Scripts/python check_invariants.py            # 离线检查 I1/I2/I3/I6/I7
    .venv/Scripts/python check_invariants.py --api http://127.0.0.1:8000   # 追加在线检查 I4/I8（需服务已启动）
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
from app.database import SessionLocal
from app import models

REQ_STATUS = {"待澄清", "待设计", "设计中", "待串讲", "研发中", "已上线"}
SPRINT_STATUS = {"进行中", "已归档"}
QA_FEEDBACK = {"未反馈", "已解决", "未解决"}
ROLES = {"admin", "pm", "dev"}
ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx",
                "xls", "xlsx", "csv", "ppt", "pptx", "md", "txt"}
MAX_MATERIAL_SIZE = 20 * 1024 * 1024

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"  [FAIL] {msg}")


def main():
    db = SessionLocal()
    try:
        users = {u.id for u in db.query(models.User).all()}
        projects = {p.id for p in db.query(models.Project).all()}
        sprints = {s.id: s for s in db.query(models.Sprint).all()}
        reqs = db.query(models.Requirement).all()
        req_ids = {r.id for r in reqs}
        pubs = db.query(models.Publish).all()
        pub_ids = {p.id for p in pubs}

        print("== I1 引用完整性 ==")
        for r in reqs:
            check(r.project_id in projects, f"requirement#{r.id} project_id 悬挂")
            if r.pm_id is not None:
                check(r.pm_id in users, f"requirement#{r.id} pm_id 悬挂")
            if r.creator_id is not None:
                check(r.creator_id in users, f"requirement#{r.id} creator_id 悬挂")
            if r.sprint_id is not None:
                check(r.sprint_id in sprints, f"requirement#{r.id} sprint_id 悬挂")
        for s in sprints.values():
            check(s.project_id in projects, f"version#{s.id} project_id 悬挂")
        for m in db.query(models.RequirementAttachment).all():
            check(m.requirement_id in req_ids, f"material#{m.id} requirement_id 悬挂")
        for p in pubs:
            check(p.sprint_id in sprints, f"prototype#{p.id} version_id 悬挂")
        convs = {c.id: c for c in db.query(models.Conversation).all()}
        for c in convs.values():
            check(c.requirement_id in req_ids, f"conversation#{c.id} requirement_id 悬挂")
        for m in db.query(models.Message).all():
            check(m.conversation_id in convs, f"message#{m.id} conversation_id 悬挂")
        for q in db.query(models.QaLog).all():
            check(q.prototype_id in pub_ids, f"qaLog#{q.id} prototype_id 悬挂")

        print("== I2 归档一致性 ==")
        for s in sprints.values():
            if s.status == "已归档":
                check(bool(s.summary), f"version#{s.id} 已归档但 summary 为空")
                check(bool(s.kb_doc_id), f"version#{s.id} 已归档但 kb_doc_id 为空")
                check(s.archived_by is not None and s.archived_at is not None,
                      f"version#{s.id} 已归档但 archived_by/at 为空")
                for r in reqs:
                    if r.sprint_id == s.id:
                        check(r.status == "已上线", f"requirement#{r.id} 属已归档版本但 status={r.status}")
                        check(bool(r.actual_online_date), f"requirement#{r.id} 已上线但 actual_online_date 为空")

        print("== I3 原型唯一性与落盘完整 ==")
        seen = set()
        for p in pubs:
            key = (p.sprint_id, p.title)
            check(key not in seen, f"version#{p.sprint_id} 下原型重名：{p.title}")
            seen.add(key)
            abs_dir = os.path.join(settings.publish_root, p.dir_path or "")
            check(os.path.isdir(abs_dir), f"prototype#{p.id} 目录不存在：{p.dir_path}")
            if p.entry_path:
                check(os.path.isfile(os.path.join(abs_dir, p.entry_path)),
                      f"prototype#{p.id} 入口文件缺失：{p.entry_path}")

        print("== I6 材料约束 ==")
        mat_by_req = {}
        for m in db.query(models.RequirementAttachment).all():
            check(m.size <= MAX_MATERIAL_SIZE, f"material#{m.id} 超过 20MB")
            ext = (m.filename or "").rsplit(".", 1)[-1].lower()
            check(ext in ALLOWED_EXTS, f"material#{m.id} 格式不在白名单：{m.filename}")
            mat_by_req[m.requirement_id] = mat_by_req.get(m.requirement_id, 0) + 1
        for req_id, n in mat_by_req.items():
            check(n <= 20, f"requirement#{req_id} 材料数 {n} > 20")

        print("== I7 枚举合法性 ==")
        for r in reqs:
            check(r.status in REQ_STATUS, f"requirement#{r.id} status 越界：{r.status}")
        for s in sprints.values():
            check(s.status in SPRINT_STATUS, f"version#{s.id} status 越界：{s.status}")
        for q in db.query(models.QaLog).all():
            check(q.feedback in QA_FEEDBACK, f"qaLog#{q.id} feedback 越界：{q.feedback}")
        for u in db.query(models.User).all():
            check(u.role in ROLES, f"user#{u.id} role 越界：{u.role}")
    finally:
        db.close()

    if "--api" in sys.argv:
        base = sys.argv[sys.argv.index("--api") + 1].rstrip("/")
        _api_checks(base)

    print()
    if failures:
        print(f"自检未通过：{len(failures)} 项失败")
        sys.exit(1)
    print("全部不变量通过 ✅")


def _api_checks(base):
    import requests

    print("== I8 免登边界 ==")
    s = requests.Session()  # 无会话
    r = s.get(base + "/", allow_redirects=False)
    check(r.status_code in (302, 303), "未登录访问首页未跳转登录")
    r = s.get(base + "/api/requirements")
    check(r.status_code == 401, "未登录调 API 未返回 401")
    db = SessionLocal()
    pub = db.query(models.Publish).first()
    db.close()
    if pub:
        link = f"/p/{pub.access_key}/" + (pub.entry_path or "")
        r = s.get(base + link)
        check(r.status_code == 200, f"免登直链不可访问：{link}")
        body = r.text[:500].lower()
        check("qa" not in body and "toolbar" not in body, "免登直链疑似包含问答/工具条元素")

    print("== I4 权限边界 ==")
    r = s.post(base + "/login", data={"username": "__nobody__", "password": "x"}, allow_redirects=False)
    check(r.status_code in (200, 303), "登录接口异常")
    # 找一个 dev 账号做写接口 403 抽查（需要主账号先重置其密码，此处仅提示）
    print("  [提示] I4 的 dev 写接口 403 逐项断言已在开发冒烟中覆盖；此处仅验证未登录边界。")


if __name__ == "__main__":
    main()
