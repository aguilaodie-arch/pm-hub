"""钉钉企业内部应用「工作通知」推送（D22）。

配置在 config.yaml 的 dingtalk 段（配置中心 → 钉钉推送 Tab 维护）：
  app_key / app_secret / agent_id / hub_base_url
推送通道仅为工作通知（corpconversation/asyncsend_v2），不做群推送、不做机器人单聊。
"""
import time

import requests

from .config import settings

_token_cache = {"token": None, "exp": 0.0}


def _cfg():
    return settings.dingtalk or {}


def configured():
    c = _cfg()
    return bool((c.get("app_key") or "").strip() and (c.get("app_secret") or "").strip() and c.get("agent_id"))


def get_token():
    c = _cfg()
    app_key = (c.get("app_key") or "").strip()
    app_secret = (c.get("app_secret") or "").strip()
    if not app_key or not app_secret:
        raise RuntimeError("钉钉应用未配置（配置中心 → 钉钉推送，填 app_key / app_secret）")
    if _token_cache["token"] and time.time() < _token_cache["exp"] - 60:
        return _token_cache["token"]
    r = requests.get(
        "https://oapi.dingtalk.com/gettoken",
        params={"appkey": app_key, "appsecret": app_secret},
        timeout=10,
    )
    data = r.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"获取钉钉 access_token 失败：{data.get('errmsg')}（errcode={data.get('errcode')}）")
    _token_cache["token"] = data["access_token"]
    _token_cache["exp"] = time.time() + int(data.get("expires_in", 7200))
    return _token_cache["token"]


def send_work_notification(userid, title, markdown_text):
    """给指定钉钉 userid 发工作通知（markdown 消息）。成功返回 task_id，失败抛异常。"""
    c = _cfg()
    agent_id = c.get("agent_id")
    if not agent_id:
        raise RuntimeError("钉钉 agent_id 未配置（配置中心 → 钉钉推送）")
    if not (userid or "").strip():
        raise RuntimeError("接收人未配置钉钉 userid（配置中心 → 账号管理）")
    token = get_token()
    payload = {
        "agent_id": int(agent_id),
        "userid_list": userid.strip(),
        "msg": {"msgtype": "markdown", "markdown": {"title": title, "text": markdown_text}},
    }
    r = requests.post(
        "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2",
        params={"access_token": token},
        json=payload,
        timeout=10,
    )
    data = r.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"工作通知发送失败：{data.get('errmsg')}（errcode={data.get('errcode')}）")
    return data.get("task_id")


def test_push(userid):
    """配置中心测试推送：分步日志（与 LLM 连通性测试同款交互）。"""
    steps = []

    def step(name, ok, detail=""):
        steps.append({"name": name, "ok": ok, "detail": detail})
        return ok

    c = _cfg()
    if not step(
        "检查配置",
        bool((c.get("app_key") or "").strip() and (c.get("app_secret") or "").strip() and c.get("agent_id")),
        "app_key / app_secret / agent_id 均已填写"
        if configured()
        else "app_key、app_secret、agent_id 三项都需要填写",
    ):
        return {"ok": False, "steps": steps, "error": "钉钉应用配置不完整"}
    if not (userid or "").strip():
        step("检查接收人", False, "请填写用于测试的钉钉 userid")
        return {"ok": False, "steps": steps, "error": "未填写测试 userid"}
    step("检查接收人", True, f"userid={userid.strip()}")
    try:
        get_token()
        step("获取 access_token", True, "应用凭证有效")
    except Exception as e:
        step("获取 access_token", False, str(e))
        return {"ok": False, "steps": steps, "error": str(e)}
    try:
        task_id = send_work_notification(
            userid,
            "PM Hub 推送测试",
            "### PM Hub 推送测试\n\n这是一条测试消息：钉钉工作通知通道已配置成功。\n\n"
            "后续研发问答「未解决」升级将通过此通道推送给对应产品经理。",
        )
        step("发送工作通知", True, f"已发出，task_id={task_id}")
        return {"ok": True, "steps": steps}
    except Exception as e:
        step("发送工作通知", False, str(e))
        return {"ok": False, "steps": steps, "error": str(e)}
