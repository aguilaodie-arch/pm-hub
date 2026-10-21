# -*- coding: utf-8 -*-
"""导入 specs/pm-hub/05-seed-data.yaml 种子数据（幂等；不覆盖已有数据）。

用法：.venv/Scripts/python seed.py
注意：种子里的材料文件与原型目录会生成占位内容，保证下载/直链/不变量可跑通。
"""
import os
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
from app.database import SessionLocal, init_db
from app import models, security

SEED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs", "pm-hub", "05-seed-data.yaml")
DEFAULT_PASSWORD = "pmhub12345"  # 种子账号初始密码（≥8 位），登录后请自行修改


def attach_root():
    root = os.path.join(os.path.dirname(settings.publish_root), "attachments")
    os.makedirs(root, exist_ok=True)
    return root


def main():
    init_db()
    with open(SEED_PATH, encoding="utf-8") as f:
        seed = yaml.safe_load(f)
    db = SessionLocal()
    uid, pid, vid, rid, prid, cid = {}, {}, {}, {}, {}, {}
    try:
        # 账号
        for a in seed.get("account", []):
            u = db.query(models.User).filter_by(username=a["username"]).first()
            if not u:
                ph, salt = security.hash_password(DEFAULT_PASSWORD)
                u = models.User(username=a["username"], display_name=a["name"], role=a["role"],
                                active=a.get("active", True), salt=salt, password_hash=ph)
                db.add(u)
                db.flush()
                print(f"  [+] 账号 {a['username']}（{a['role']}），初始密码 {DEFAULT_PASSWORD}")
            uid[a["id"]] = u.id
        # 项目
        for p in seed.get("project", []):
            pr = db.query(models.Project).filter_by(name=p["name"]).first()
            if not pr:
                pr = models.Project(name=p["name"], description="")
                db.add(pr)
                db.flush()
                print(f"  [+] 项目 {p['name']}")
            pid[p["id"]] = pr.id
        # 版本
        from datetime import datetime as _dt

        def _ts(v):
            return _dt.strptime(v, "%Y-%m-%d %H:%M") if v else None

        for v in seed.get("version", []):
            sv = db.query(models.Sprint).filter_by(project_id=pid[v["projectId"]], name=v["name"]).first()
            if not sv:
                sv = models.Sprint(project_id=pid[v["projectId"]], name=v["name"], status=v["status"],
                                   summary=v.get("summary"), kb_doc_id=v.get("kbDocId"),
                                   archived_by=uid.get(v.get("archivedBy")),
                                   archived_at=_ts(v.get("archivedAt")))
                db.add(sv)
                db.flush()
                print(f"  [+] 版本 {v['name']}（{v['status']}）")
            vid[v["id"]] = sv.id
        # 需求
        for q in seed.get("requirement", []):
            rq = db.query(models.Requirement).filter_by(req_no=q["id"]).first()
            if not rq:
                rq = models.Requirement(
                    req_no=q["id"], title=q["title"], project_id=pid[q["projectId"]],
                    sprint_id=vid.get(q.get("versionId")), pm_id=uid.get(q.get("pmId")),
                    status=q["status"], priority=q["priority"], requester=q.get("requester"),
                    description=q.get("description"), value=q.get("value"),
                    jira_key=q.get("jiraUrl"), planned_online_date=q.get("plannedOnlineDate"),
                    actual_online_date=q.get("actualOnlineDate"), creator_id=uid.get(q.get("createdBy")),
                )
                db.add(rq)
                db.flush()
                print(f"  [+] 需求 {q['id']} {q['title'][:20]}")
            rid[q["id"]] = rq.id
        # 材料（生成占位文件）
        for m in seed.get("material", []):
            req_id = rid.get(m["requirementId"])
            exists = db.query(models.RequirementAttachment).filter_by(
                requirement_id=req_id, filename=m["fileName"]).first()
            if req_id and not exists:
                rel = os.path.join(str(req_id), m["fileName"])
                dst = os.path.join(attach_root(), rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.exists(dst):
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(f"种子占位文件：{m['fileName']}\n")
                size = os.path.getsize(dst)
                db.add(models.RequirementAttachment(
                    requirement_id=req_id, filename=m["fileName"], stored_path=rel,
                    size=size, uploader_id=uid.get(m.get("uploadedBy"))))
                print(f"  [+] 材料 {m['fileName']}（占位 {size}B）")
        # 原型（生成最小可访问目录）
        import uuid as _uuid
        for p in seed.get("prototype", []):
            ver_id = vid.get(p["versionId"])
            exists = db.query(models.Publish).filter_by(sprint_id=ver_id, title=p["name"]).first()
            if ver_id and not exists:
                key = _uuid.uuid4().hex
                rel = os.path.join(str(pid_of(db, ver_id)), str(ver_id), key)
                dst = os.path.join(settings.publish_root, rel)
                os.makedirs(dst, exist_ok=True)
                entry = p.get("entryPath") or "index.html"
                entry_abs = os.path.join(dst, entry)
                os.makedirs(os.path.dirname(entry_abs), exist_ok=True)
                if not os.path.exists(entry_abs):
                    with open(entry_abs, "w", encoding="utf-8") as f:
                        f.write(f"<html><body><h1>{p['name']}（种子占位原型）</h1></body></html>")
                fc = sum(len(files) for _, _, files in os.walk(dst))
                ts = sum(os.path.getsize(os.path.join(r, fn)) for r, _, files in os.walk(dst) for fn in files)
                pub = models.Publish(sprint_id=ver_id, publisher_id=uid.get(p.get("uploadedBy")),
                                     title=p["name"], access_key=key, dir_path=rel,
                                     entry_path=entry, file_count=fc, total_size=ts,
                                     extracted_text=p["name"])
                db.add(pub)
                db.flush()
                prid[p["id"]] = pub.id
                print(f"  [+] 原型 {p['name']}（{fc} 文件）")
            elif ver_id:
                prid[p["id"]] = exists.id
        # 预设计对话与消息
        for c in seed.get("conversation", []):
            req_id = rid.get(c["requirementId"])
            cv = db.query(models.Conversation).filter_by(requirement_id=req_id, title=c["title"]).first()
            if req_id and not cv:
                cv = models.Conversation(requirement_id=req_id, title=c["title"],
                                         created_by=uid.get(c.get("createdBy")))
                db.add(cv)
                db.flush()
                print(f"  [+] 对话 {c['title'][:20]}")
            if cv:
                cid[c["id"]] = cv.id
        for m in seed.get("message", []):
            cv_id = cid.get(m["conversationId"])
            if cv_id and not db.query(models.Message).filter_by(conversation_id=cv_id, content=m["content"]).first():
                db.add(models.Message(conversation_id=cv_id, role=m["role"], content=m["content"],
                                      author_id=uid.get(m.get("authorId"))))
        # 问答记录
        for q in seed.get("qaLog", []):
            proto_id = prid.get(q["prototypeId"])
            if proto_id and not db.query(models.QaLog).filter_by(prototype_id=proto_id, question=q["question"]).first():
                db.add(models.QaLog(prototype_id=proto_id, question=q["question"], answer=q.get("answer"),
                                    feedback=q["feedback"], asked_by=uid.get(q.get("askedBy")),
                                    handled_by=uid.get(q.get("handledBy"))))
                print(f"  [+] 问答记录（{q['feedback']}）")
        db.commit()
        print("\n种子数据导入完成。")
        print(f"种子账号初始密码统一为：{DEFAULT_PASSWORD}（admin 账号若已存在则密码不变）")
    finally:
        db.close()


def pid_of(db, sprint_id):
    s = db.query(models.Sprint).get(sprint_id)
    return s.project_id if s else 0


if __name__ == "__main__":
    main()
