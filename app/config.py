import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

_DEFAULT_SKILLS = [
    {
        "key": "brainstorm",
        "name": "脑暴",
        "description": "发散式脑暴：围绕需求从场景、价值、方案、风险等角度出点子",
        "prompt": "【技能·脑暴】请围绕该需求做发散式脑暴：从用户场景、业务价值、方案方向、潜在风险等角度给出至少 8 个点子，鼓励非常规思路，每个点子附一句话说明。",
        "enabled": True,
    },
    {
        "key": "grill",
        "name": "Grill-me",
        "description": "犀利评审：对需求刨根问底，暴露边界、漏洞与异常场景",
        "prompt": "【技能·Grill-me】请扮演一位犀利的技术评审负责人，针对当前需求及已有讨论提出至少 8 个尖锐问题，挑战需求边界、逻辑漏洞、异常场景、数据一致性、权限与性能。只提问，不给答案。",
        "enabled": True,
    },
    {
        "key": "prd",
        "name": "PRD 编写",
        "description": "基于需求与讨论输出结构完整的 PRD 草稿",
        "prompt": "【技能·PRD 编写】请基于需求信息与以上讨论，输出一份结构完整的 PRD 草稿（Markdown）：背景与目标、用户故事、功能范围（In Scope / Out of Scope）、详细业务逻辑与交互规则、异常流、数据口径、埋点建议、风险与依赖。请将完整 PRD 用 ```file:PRD.md 代码围栏包裹输出，说明文字放在围栏之外。",
        "enabled": True,
    },
    {
        "key": "bdd",
        "name": "BDD 编写",
        "description": "用 Gherkin 语法编写核心场景的 BDD 用例",
        "prompt": "【技能·BDD 编写】请基于需求信息与以上讨论，使用 Gherkin 语法（Feature / Scenario / Given / When / Then）编写核心场景的 BDD 用例，覆盖主流程与关键异常流。请将用例用 ```file:验收用例.feature 代码围栏包裹输出，说明文字放在围栏之外。",
        "enabled": True,
    },
]

_DEFAULT_AGENT2_SYSTEM_PROMPT = (
    "你是项目的研发答疑助手。研发同学在查看原型时会直接提问，通常不带背景上下文。\n"
    "要求：1) 仅基于下方提供的资料回答，回答时注明依据来源（如：原型页面 / 需求「xx」/ 附件《xx》）；"
    "2) 资料不足以回答时，明确说明「现有资料中没有找到相关内容」，并建议研发联系对应的产品经理确认，不要编造；"
    "3) 使用中文，面向研发实现视角，简洁务实，不要寒暄。"
)

_DEFAULT_SUMMARY_TEMPLATE = (
    "你是资深产品经理助手。请基于以下版本资料，输出版本归档摘要（Markdown，中文，不要寒暄），结构固定为：\n"
    "# {version} 版本摘要\n"
    "## 版本概述\n"
    "（一段话概述本版本目标与整体变更）\n"
    "## 需求明细\n"
    "（逐需求一段，每段包含：背景 / 方案要点 / 关键口径与枚举 / 涉及页面）"
)

# D22：研发问答升级的 AC 式摘要模板（配置中心可调）
_DEFAULT_AC_TEMPLATE = (
    "你是产品经理助手。请把一次「研发提问未被 AI 解答」的记录整理为 AC（验收口径）式问题摘要，"
    "供产品经理快速进入解题状态。\n"
    "严格按以下结构输出（Markdown，中文，不要寒暄）：\n"
    "## 谁\n（提问人及其角色视角）\n"
    "## 前置条件\n（在哪个原型 / 哪个页面 / 什么数据状态下）\n"
    "## 操作与逻辑\n（研发做了什么；按原型逻辑应该怎样）\n"
    "## 预期 vs 实际\n（期望的结果；AI 未能解答的卡点）\n"
    "## 待裁决问题\n（一句话归纳需要产品经理拍板的问题）\n"
    "只基于提供的问答记录与背景资料，不要编造；记录中缺失的信息写「（记录中未体现）」。"
)

# D23：转 Jira 用户故事生成模板（配置中心可调）
_DEFAULT_JIRA_STORY_TEMPLATE = (
    "你是产品经理助手。请根据提供的需求信息，生成一份可直接写入 Jira 的用户故事（Markdown，中文）。\n"
    "严格按以下结构输出（不要寒暄，不要解释）：\n"
    "## 用户故事\n作为……我希望……以便……\n"
    "## 背景与价值\n（为什么做，解决什么问题）\n"
    "## 功能描述\n（做什么、不做什么，按要点列出）\n"
    "## 业务规则与口径\n（关键规则、边界、数据口径）\n"
    "## 验收标准\n（Given/When/Then 或逐条可验证的验收点）\n"
    "只基于提供的需求信息与材料摘录，不要编造；缺失的信息写「（待补充）」。"
)

_defaults = {
    "host": "0.0.0.0",
    "port": 8000,
    "secret_key": "change-me-in-production-please-randomize",
    "publish_root": os.path.join(BASE_DIR, "data", "publish"),
    "chroma_dir": os.path.join(BASE_DIR, "data", "chroma"),
    "db_url": f"sqlite:///{os.path.join(BASE_DIR, 'data', 'app.db')}",
    "bootstrap_admin": {"username": "admin", "password": "admin123", "display_name": "管理员"},
    # 总结与问答模型（API 调用，兼容 OpenAI 格式）
    "ai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "chat_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
    },
    # 向量模型：本地 ONNX（模型文件随项目存放，不走 API）
    "embedding": {
        "provider": "local_onnx",
        "model_path": os.path.join(BASE_DIR, "models", "jina-embeddings-v2-base-zh"),
    },
    # 预设计 Agent（Agent-1）
    "design_agent": {
        "description": "",
        "base_url": "",
        "api_key": "",
        "chat_model": "",
        "use_kb": True,
        "max_iterations": 1,
        "max_input_length": 24000,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 3000,
        "skills": _DEFAULT_SKILLS,
    },
    # 原型问答 Agent（Agent-2）
    "agent2": {
        "system_prompt": _DEFAULT_AGENT2_SYSTEM_PROMPT,
        "use_kb": True,
    },
    # 归档
    "archive": {
        "summary_template": _DEFAULT_SUMMARY_TEMPLATE,
    },
    # 知识库检索与切块超参数（D20：配置中心可调，新归档/重建的条目生效）
    "knowledge": {
        "top_k": 5,
        "chunk_size": 1200,
        "chunk_overlap": 200,
    },
    # 钉钉推送（D22：企业内部应用工作通知；hub_base_url 用于消息内跳转链接）
    "dingtalk": {
        "app_key": "",
        "app_secret": "",
        "agent_id": "",
        "hub_base_url": "",
    },
    # 问答升级（D22：AC 式摘要模板）
    "escalate": {
        "ac_template": _DEFAULT_AC_TEMPLATE,
    },
    # Jira 联动（D23：全局单一目标项目；api_token 界面掩码不回显）
    "jira": {
        "base_url": "",
        "email": "",
        "api_token": "",
        "project_key": "",
        "story_template": _DEFAULT_JIRA_STORY_TEMPLATE,
    },
}


def _deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _deep_update(d[k], v)
        else:
            d[k] = v


def _abs_paths(cfg):
    cfg["publish_root"] = os.path.abspath(cfg["publish_root"])
    if cfg["db_url"].startswith("sqlite:///"):
        rel = cfg["db_url"].replace("sqlite:///", "", 1)
        cfg["db_url"] = "sqlite:///" + os.path.abspath(rel)
    cfg["chroma_dir"] = os.path.abspath(cfg["chroma_dir"])
    mp = cfg.get("embedding", {}).get("model_path", "")
    if mp:
        cfg["embedding"]["model_path"] = os.path.abspath(mp)
    return cfg


def load_config():
    cfg = dict(_defaults)
    user = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        _deep_update(cfg, user)
    # 兼容旧的 ai_design 段：迁移到 design_agent
    legacy = user.get("ai_design") or {}
    if legacy and "design_agent" not in user:
        for k in ("base_url", "api_key", "chat_model"):
            if legacy.get(k):
                cfg["design_agent"][k] = legacy[k]
    return _abs_paths(cfg)


class Settings:
    host = _defaults["host"]
    port = _defaults["port"]
    secret_key = _defaults["secret_key"]
    publish_root = _abs_paths(dict(_defaults))["publish_root"]
    db_url = _abs_paths(dict(_defaults))["db_url"]
    chroma_dir = _defaults["chroma_dir"]
    bootstrap_admin = _defaults["bootstrap_admin"]
    ai_base_url = _defaults["ai"]["base_url"]
    ai_api_key = _defaults["ai"]["api_key"]
    chat_model = _defaults["ai"]["chat_model"]
    embedding_model = _defaults["ai"]["embedding_model"]
    ai_enabled = False
    embedding_provider = _defaults["embedding"]["provider"]
    embedding_model_path = _defaults["embedding"]["model_path"]
    design_agent = _defaults["design_agent"]
    design_enabled = False
    agent2 = _defaults["agent2"]
    archive = _defaults["archive"]
    knowledge = _defaults["knowledge"]
    dingtalk = _defaults["dingtalk"]
    escalate = _defaults["escalate"]
    jira = _defaults["jira"]


settings = Settings()


def reload_config():
    """重新读取 config.yaml 并热更新（模型配置可立即生效，host/port/路径需重启）。"""
    cfg = load_config()
    settings.host = cfg["host"]
    settings.port = cfg["port"]
    settings.secret_key = cfg["secret_key"]
    settings.publish_root = cfg["publish_root"]
    settings.db_url = cfg["db_url"]
    settings.chroma_dir = cfg["chroma_dir"]
    settings.bootstrap_admin = cfg["bootstrap_admin"]
    settings.ai_base_url = cfg["ai"]["base_url"]
    settings.ai_api_key = cfg["ai"]["api_key"]
    settings.chat_model = cfg["ai"]["chat_model"]
    settings.embedding_model = cfg["ai"]["embedding_model"]
    settings.ai_enabled = bool(cfg["ai"]["api_key"])
    settings.embedding_provider = cfg["embedding"]["provider"]
    settings.embedding_model_path = cfg["embedding"]["model_path"]
    settings.design_agent = cfg["design_agent"]
    settings.agent2 = cfg["agent2"]
    settings.archive = cfg["archive"]
    settings.knowledge = cfg["knowledge"]
    settings.dingtalk = cfg["dingtalk"]
    settings.escalate = cfg["escalate"]
    settings.jira = cfg["jira"]
    settings.design_enabled = bool(
        cfg["ai"]["api_key"] or cfg["design_agent"].get("api_key")
    )
    return settings


def save_config(updates: dict):
    """把管理页面提交的设置写回 config.yaml。"""
    current = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            current = yaml.safe_load(f) or {}
    for k in ("host", "port", "secret_key", "publish_root"):
        if k in updates and updates[k] != "":
            current[k] = updates[k]
    if "ai" in updates:
        current.setdefault("ai", {})
        for k in ("base_url", "api_key", "chat_model", "embedding_model"):
            if k in updates["ai"] and updates["ai"][k] != "":
                current["ai"][k] = updates["ai"][k]
    if "embedding" in updates:
        current.setdefault("embedding", {})
        for k in ("provider", "model_path"):
            if k in updates["embedding"] and updates["embedding"][k] != "":
                current["embedding"][k] = updates["embedding"][k]
    if "design_agent" in updates:
        current.setdefault("design_agent", {})
        for k, v in updates["design_agent"].items():
            current["design_agent"][k] = v  # 全部允许覆盖（含置空/技能列表替换）
    for section in ("agent2", "archive", "knowledge", "dingtalk", "escalate", "jira"):
        if section in updates:
            current.setdefault(section, {})
            for k, v in updates[section].items():
                current[section][k] = v
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("# Axure 原型发布平台配置（模型配置保存后立即生效；host/port/路径需重启服务）\n")
        yaml.safe_dump(current, f, allow_unicode=True, sort_keys=False)
    reload_config()
