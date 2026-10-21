from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128))
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    role = Column(String(16), default="pm")  # admin | pm | dev（原 member 已迁移为 pm）
    active = Column(Boolean, default=True)   # 停用后不可登录，历史数据保留署名
    dingtalk_userid = Column(String(64), default="")  # 钉钉 userid（D22：升级推送接收人映射，账号管理手工配置）
    created_at = Column(DateTime, default=_utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class Sprint(Base):
    """版本（迭代容器，归档单位），对应 Spec 的 version。"""
    __tablename__ = "sprints"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    status = Column(String(16), default="进行中")              # 进行中 | 已归档（单向流转）
    summary = Column(Text)                                     # 归档摘要全文，归档后才有值
    kb_doc_id = Column(String(128))                            # 摘要写入知识库后返回的文档 id
    archived_by = Column(Integer, ForeignKey("users.id"))      # 归档操作人
    created_at = Column(DateTime, default=_utcnow)
    archived_at = Column(DateTime)


class Publish(Base):
    """原型发布（Axure 导出 HTML 整目录），对应 Spec 的 prototype。D34：kind 区分 Axure 原型与 HTML demo。"""
    __tablename__ = "publishes"
    id = Column(Integer, primary_key=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False)
    publisher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256))
    kind = Column(String(16), default="prototype")  # D34：prototype=Axure 原型 / demo=HTML demo（不开问答、不进知识库）
    access_key = Column(String(64), unique=True, index=True)
    dir_path = Column(String(512))
    extracted_text = Column(Text)
    entry_path = Column(String(256))              # 入口文件相对路径（index.html/start.html/唯一 .html）
    file_count = Column(Integer, default=0)       # 目录内文件总数
    total_size = Column(Integer, default=0)       # 目录总字节数
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)  # 覆盖上传时刷新
    publisher = relationship("User")


class Requirement(Base):
    """需求（需求池核心实体），对应 Spec 的 requirement（D8：主键自增整数，编号单设 req_no）。"""
    __tablename__ = "requirements"
    id = Column(Integer, primary_key=True)
    req_no = Column(String(32), index=True)                            # 需求编号 RQ+yyMMdd+4位当日序列
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), index=True)  # 为空=未排期
    title = Column(String(256), nullable=False)                        # 需求名称
    pm_id = Column(Integer, ForeignKey("users.id"))                    # 负责 PM（仅 role=pm）
    owner = Column(String(64))                                         # 【废弃】旧"产品经理"字符串列，迁移后不再使用（见 pm_id）
    submitter = Column(String(64))                                     # 【废弃】旧"提交人"，不再使用
    submit_date = Column(String(16))                                   # 【废弃】旧"提交日期"，不再使用
    requester = Column(String(128))                                    # 需求方（自由文本）
    description = Column(Text)                                         # 需求描述长文本
    status = Column(String(16), default="待澄清", index=True)          # 待澄清|待设计|设计中|待串讲|研发中|已上线
    priority = Column(String(8), default="P1")                         # P0|P1|P2（原 P3 已归并到 P2）
    jira_key = Column(String(64))                                      # JIRA 编号（D23 起存 issue key；兼容历史手填完整 URL）
    jira_sync = Column(String(16), default="")                         # D23：""=未关联 | 已关联 | 同步失败
    jira_error = Column(Text)                                          # D23：最近一次同步失败原因
    value = Column(Text)                                               # 核心价值
    planned_online_date = Column(String(16))                           # 计划上线日期 YYYY-MM-DD
    actual_online_date = Column(String(16))                            # 实际上线日期（归档联动自动写入）
    user_story = Column(Text)                                          # UserStory（预设计冷启动上下文，D6 保留）
    creator_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class RequirementAttachment(Base):
    """材料（需求维度附件），对应 Spec 的 material。"""
    __tablename__ = "requirement_attachments"
    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False, index=True)
    filename = Column(String(256))          # 原始文件名
    stored_path = Column(String(512))       # 相对 attachments 根目录的路径
    size = Column(Integer, default=0)
    uploader_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)


class Conversation(Base):
    """预设计对话（Agent-1），对应 Spec 的 conversation。"""
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False, index=True)
    title = Column(String(256))                            # 默认=需求标题，可改
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Message(Base):
    """对话消息，对应 Spec 的 message。"""
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(16))               # user | assistant
    content = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"))   # role=user 时必有值；assistant 为 null
    created_at = Column(DateTime, default=_utcnow)


class KnowledgeEntry(Base):
    """知识条目（D19：需求级知识卡 + 版本级索引），归档时生成，PM/主账号可编辑。"""
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), index=True)  # 空=版本索引条目
    req_no = Column(String(32))
    title = Column(String(256))
    kind = Column(String(16), default="requirement")    # requirement | index
    content = Column(Text)
    publish_ids = Column(Text, default="")            # JSON 列表：关联原型 id（D21，问答佐证链接）
    edited = Column(Boolean, default=False)             # 人工编辑过：重新归档不覆盖
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class QaLog(Base):
    """原型问答记录（Agent-2），对应 Spec 的 qaLog。"""
    __tablename__ = "qa_logs"
    id = Column(Integer, primary_key=True)
    prototype_id = Column(Integer, ForeignKey("publishes.id"), nullable=False, index=True)
    question = Column(Text)
    answer = Column(Text)
    feedback = Column(String(8), default="未反馈")        # 未反馈 | 已解决 | 未解决（D22 起"未解决"恢复使用=已升级）
    asked_by = Column(Integer, ForeignKey("users.id"))
    handled_by = Column(Integer, ForeignKey("users.id"))  # 标记已处理的 PM（D22 恢复使用）
    handled_at = Column(DateTime)
    summary = Column(Text)                                # D22：升级时 LLM 生成的 AC 式摘要
    push_status = Column(String(16), default="")          # D22：空=未推送 | 已推送 | 推送失败
    push_error = Column(Text)                             # D22：推送失败原因（供排查与重发）
    created_at = Column(DateTime, default=_utcnow)


class DesignMessage(Base):
    """【历史备份】旧预设计消息表，数据已迁入 conversations/messages，不再使用。"""
    __tablename__ = "design_messages"
    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False, index=True)
    role = Column(String(16))               # user | assistant
    skill = Column(String(16))              # 用户消息触发的技能，可空
    content = Column(Text)
    created_at = Column(DateTime, default=_utcnow)


class Report(Base):
    """【历史备份】旧版本报告表，内容已迁入 sprints.summary，不再使用。"""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=_utcnow)
