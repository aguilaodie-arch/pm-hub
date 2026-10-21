"""Jira REST API 联动（D23）。

配置在 config.yaml 的 jira 段（配置中心 → 集成 → Jira 维护）：
  base_url / email / api_token / project_key / story_template
一期口径：单向（PM Hub → Jira）、全局单一目标项目、只做 Story 创建与废弃联动，
永久禁止真删除 Jira issue。
"""
import requests

from .config import settings

# 废弃时尝试的"完成类"状态/流转名（按序匹配首个可用 transition）
_DONE_NAMES = ("已废弃", "废弃", "Done", "Closed", "Resolved", "完成", "关闭", "解决")


def _cfg():
    return settings.jira or {}


def configured():
    c = _cfg()
    return bool(
        (c.get("base_url") or "").strip()
        and (c.get("email") or "").strip()
        and (c.get("api_token") or "").strip()
        and (c.get("project_key") or "").strip()
    )


def issue_url(key):
    base = (_cfg().get("base_url") or "").strip().rstrip("/")
    return f"{base}/browse/{key}" if base and key else ""


def _api(method, path, **kwargs):
    """统一请求：basic 认证 + 超时 + 错误归一化为 RuntimeError。"""
    c = _cfg()
    base = (c.get("base_url") or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("Jira 未配置（配置中心 → 集成 → Jira）")
    try:
        r = requests.request(
            method,
            f"{base}/rest/api/2{path}",
            auth=(c.get("email") or "", c.get("api_token") or ""),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
            **kwargs,
        )
    except requests.exceptions.ConnectTimeout:
        raise RuntimeError("连接 Jira 超时（15s 内未建立连接）")
    except requests.exceptions.ReadTimeout:
        raise RuntimeError("Jira 响应超时（已连接，15s 内未返回）")
    except requests.exceptions.SSLError:
        raise RuntimeError("Jira HTTPS 证书校验失败")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"无法连接 Jira：{str(e)[:120]}")
    if r.status_code in (401, 403):
        raise RuntimeError(f"Jira 鉴权失败（HTTP {r.status_code}），检查 email / api_token")
    if r.status_code == 404:
        raise RuntimeError(f"Jira 资源不存在（HTTP 404）：{path}")
    if r.status_code >= 400:
        excerpt = (r.text or "").strip().replace("\n", " ")[:200]
        raise RuntimeError(f"Jira 返回 HTTP {r.status_code}：{excerpt}")
    return r.json() if r.text.strip() else {}


def create_story(summary, description):
    """在配置的目标项目下创建 Story，返回 issue key。"""
    c = _cfg()
    project_key = (c.get("project_key") or "").strip()
    if not project_key:
        raise RuntimeError("Jira 目标项目 project_key 未配置")
    data = _api("POST", "/issue", json={
        "fields": {
            "project": {"key": project_key},
            "summary": summary[:255],
            "description": description,
            "issuetype": {"name": "Story"},
        },
    })
    key = data.get("key")
    if not key:
        raise RuntimeError("Jira 创建响应缺少 issue key")
    return key


def add_comment(key, body):
    _api("POST", f"/issue/{key}/comment", json={"body": body})


def abandon_story(key, comment):
    """把 Story 流转到完成类状态并追加说明评论。找不到可用流转时仅追加评论。"""
    data = _api("GET", f"/issue/{key}/transitions")
    transitions = data.get("transitions") or []
    chosen = None
    for name in _DONE_NAMES:
        for t in transitions:
            if (t.get("name") or "").strip().lower() == name.lower():
                chosen = t
                break
            to = (t.get("to") or {}).get("name") or ""
            if to.strip().lower() == name.lower():
                chosen = t
                break
        if chosen:
            break
    if not chosen:
        # 兜底：目标状态类别为 done 的任意流转
        for t in transitions:
            cat = ((t.get("to") or {}).get("statusCategory") or {}).get("key")
            if cat == "done":
                chosen = t
                break
    if chosen:
        _api("POST", f"/issue/{key}/transitions", json={"transition": {"id": chosen["id"]}})
    add_comment(key, comment)
    return chosen.get("name") if chosen else ""


def test_connection():
    """配置中心测试连接：分步日志（检查配置→认证→项目校验），不真建 issue。"""
    steps = []

    def step(name, ok, detail=""):
        steps.append({"name": name, "ok": ok, "detail": detail})
        return ok

    c = _cfg()
    if not step(
        "检查配置",
        configured(),
        "base_url / email / api_token / project_key 均已填写"
        if configured()
        else "base_url、email、api_token、project_key 四项都需要填写",
    ):
        return {"ok": False, "steps": steps, "error": "Jira 配置不完整"}
    try:
        me = _api("GET", "/myself")
        step("认证", True, f"登录身份：{me.get('displayName') or me.get('name') or me.get('emailAddress') or '未知'}")
    except Exception as e:
        step("认证", False, str(e))
        return {"ok": False, "steps": steps, "error": str(e)}
    key = (c.get("project_key") or "").strip()
    try:
        proj = _api("GET", f"/project/{key}")
        step("校验目标项目", True, f"{proj.get('key')} · {proj.get('name')}")
    except Exception as e:
        step("校验目标项目", False, str(e))
        return {"ok": False, "steps": steps, "error": str(e)}
    return {"ok": True, "steps": steps}
