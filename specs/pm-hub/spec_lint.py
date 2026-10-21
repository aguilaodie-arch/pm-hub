#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_lint.py — 八件套 Spec 覆盖度检查器
用法: python spec_lint.py <spec目录>
退出码: 0=无error, 1=有error或目录无效
检查项:
  F1 文件齐全性(8件+decisions.md)
  Y1 01/05 YAML 可解析
  E1 种子数据实体 ⊆ 数据模型实体
  E2 种子记录字段 ⊆ 模型字段(未知字段警告, _scenario 豁免)
  E3 种子记录枚举值 ⊆ 模型声明枚举值
  E4 种子数据 ref 引用完整性(指向同文件内存在的记录 id)
  S1 02 状态机状态名 ⊆ 01 中 status 枚举值
  S2 种子数据覆盖每个 status 枚举的全部状态
  C1 03/06 中 实体.字段 引用在 01 中存在
  P1 04 操作规约表"校验"列非空
  P2 07 验收路径路由 ⊆ 04 页面清单路由
  D1 种子记录带 _scenario 场景标注
  A1 假设/待确认标记统计(信息)
"""
import sys, re, io
from pathlib import Path

try:
    import yaml
except ImportError:
    print("缺少 pyyaml: pip install pyyaml")
    sys.exit(2)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REQUIRED = ["00-overview.md", "01-domain-model.yaml", "02-state-machines.md",
            "03-calculations.md", "04-pages.md", "05-seed-data.yaml",
            "06-invariants.md", "07-story.md"]

errors, warns, infos = [], [], []

def err(m):  errors.append(m)
def warn(m): warns.append(m)
def info(m): infos.append(m)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def md_table_rows(text: str):
    """返回所有 markdown 表格数据行(不含表头/分隔行), 每行为 strip 后的单元格列表"""
    rows = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("|") and s.endswith("|") and not re.match(r"^\|[\s:\-|]+\|$", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            rows.append(cells)
    return rows

def main():
    if len(sys.argv) < 2:
        print("用法: python spec_lint.py <spec目录>"); sys.exit(2)
    d = Path(sys.argv[1])
    if not d.is_dir():
        print(f"目录不存在: {d}"); sys.exit(2)

    # F1 文件齐全
    for f in REQUIRED:
        if not (d / f).exists(): err(f"[F1] 缺少必需文件: {f}")
    if not (d / "decisions.md").exists():
        warn("[F1] 缺少 decisions.md（实现期决策日志，建议随八件套一起建立）")
    missing_required = [f for f in REQUIRED if not (d / f).exists()]
    if missing_required:
        report(d); sys.exit(1)

    # Y1 YAML 解析
    model = seed = None
    try:
        model = yaml.safe_load(read(d / "01-domain-model.yaml")) or {}
    except Exception as e:
        err(f"[Y1] 01-domain-model.yaml 解析失败: {e}")
    try:
        seed = yaml.safe_load(read(d / "05-seed-data.yaml")) or {}
    except Exception as e:
        err(f"[Y1] 05-seed-data.yaml 解析失败: {e}")
    if model is None or seed is None:
        report(d); sys.exit(1)

    entities = (model.get("entities") or {})
    model_fields = {e: set(((v or {}).get("fields") or {}).keys()) for e, v in entities.items()}
    model_enums  = {e: {f: (fv or {}).get("values") for f, fv in ((v or {}).get("fields") or {}).items()
                        if (fv or {}).get("type") == "enum"} for e, v in entities.items()}
    model_refs   = {e: {f: (fv or {}).get("ref") for f, fv in ((v or {}).get("fields") or {}).items()
                        if (fv or {}).get("type") == "ref"} for e, v in entities.items()}

    # E1 种子实体 ⊆ 模型
    for e in (seed or {}):
        if e not in entities:
            err(f"[E1] 种子数据实体 '{e}' 在 01-domain-model.yaml 中不存在")

    # E2/E3/E4/D1 逐条种子记录
    seed_ids = {e: set() for e in entities}
    for e, recs in (seed or {}).items():
        if e not in entities or not isinstance(recs, list): continue
        for i, r in enumerate(recs):
            if not isinstance(r, dict): continue
            rid = r.get("id", f"#{i}")
            if "id" in r: seed_ids[e].add(str(r["id"]))
            for f in r:
                if f == "_scenario": continue
                if f not in model_fields.get(e, set()):
                    warn(f"[E2] {e}.{rid}: 字段 '{f}' 未在模型中声明")
            for f, vals in model_enums.get(e, {}).items():
                if vals and f in r and r[f] is not None and str(r[f]) not in [str(v) for v in vals]:
                    err(f"[E3] {e}.{rid}: {f}={r[f]} 不在枚举 {vals} 内")
            if "_scenario" not in r:
                warn(f"[D1] {e}.{rid}: 缺少 _scenario 场景标注")

    # E4 引用完整性
    for e, refs in model_refs.items():
        for f, target in (refs or {}).items():
            if not target or "." not in target: continue
            te, tf = target.split(".", 1)
            if tf != "id":
                warn(f"[E4] {e}.{f}: ref 目标 '{target}' 非 id 字段，lint 仅支持校验 id 引用")
                continue
            for i, r in enumerate(seed.get(e) or []):
                if not isinstance(r, dict) or f not in r or r[f] is None: continue
                if te not in (seed or {}) or not seed.get(te):
                    warn(f"[E4] {e}.{f}: 目标实体 '{te}' 无种子记录，无法校验引用 {r[f]}")
                    continue
                if str(r[f]) not in seed_ids.get(te, set()):
                    err(f"[E4] {e}.{r.get('id','#%d'%i)}: {f}={r[f]} 在 {te} 种子数据中不存在")

    # S1 状态机状态名 ⊆ status 枚举; S2 种子覆盖全部状态
    sm_text = read(d / "02-state-machines.md")
    cur_entities = []
    in_enum = False
    sm_states = {}
    for ln in sm_text.splitlines():
        h = re.match(r"^#{2,3}\s+(.*)", ln)
        if h:
            title = h.group(1)
            cur_entities = [e for e in entities if e in title]
            in_enum = "状态枚举" in title
            for e in cur_entities: sm_states.setdefault(e, set())
            continue
        m = re.match(r"^\s*[-*]\s*([^：:]{1,20})[：:]", ln)
        if in_enum and m and cur_entities:
            for e in cur_entities: sm_states.setdefault(e, set()).add(m.group(1).strip())
    for e, states in sm_states.items():
        decl = []
        for f, vals in model_enums.get(e, {}).items():
            if "status" in f.lower() or "状态" in f: decl = vals or []
        if decl:
            for s in states:
                if s not in [str(v) for v in decl]:
                    warn(f"[S1] 02 状态机 '{e}' 的状态 '{s}' 不在 01 status 枚举 {decl} 内")
            seed_vals = {str(r.get("status")) for r in (seed.get(e) or []) if isinstance(r, dict) and "status" in r}
            for v in decl:
                if str(v) not in seed_vals:
                    warn(f"[S2] {e}: 种子数据未覆盖状态 '{v}'（每个状态至少一条记录才能演示全路径）")

    # C1 03/06 中 实体.字段 引用
    for fname in ["03-calculations.md", "06-invariants.md"]:
        for ent, fld in set(re.findall(r"\b([a-zA-Z]\w*)\.([a-zA-Z]\w*)", read(d / fname))):
            if ent in entities and fld not in model_fields.get(ent, set()):
                err(f"[C1] {fname}: 引用 {ent}.{fld} 在 01 中不存在")

    # P1 操作规约校验列非空
    p4 = read(d / "04-pages.md")
    sec = re.split(r"^###\s+操作规约", p4, flags=re.M)
    routes_p4 = set(re.findall(r"#/(?:pc|app|h5)/[\w-]+", p4))
    for chunk in sec[1:]:
        rows = md_table_rows(chunk.split("\n\n")[0] if "\n\n" in chunk else chunk)
        for r in rows[1:] if rows else []:
            if len(r) >= 3 and r[0] not in ("操作",) and not r[2].strip():
                warn(f"[P1] 04-pages: 操作 '{r[0]}' 的校验列为空（无校验也要写'无'）")

    # P2 story 路由 ⊆ pages 路由
    p7 = read(d / "07-story.md")
    for rt in set(re.findall(r"#/(?:pc|app|h5)/[\w-]+", p7)):
        if rt not in routes_p4:
            warn(f"[P2] 07-story 路由 '{rt}' 未在 04-pages 页面清单中登记")

    # A1 假设统计
    n_a = n_t = 0
    for f in REQUIRED + ["decisions.md"]:
        t = read(d / f)
        n_a += len(re.findall(r"【假设", t)); n_t += len(re.findall(r"【待确认", t))
    info(f"[A1] 未决标记: 【假设】x{n_a}, 【待确认】x{n_t}" + ("（冻结前应清零或显式接受默认）" if n_a + n_t else ""))

    report(d)
    sys.exit(1 if errors else 0)

def report(d):
    print(f"\n===== Spec Lint 报告: {d} =====")
    for m in errors: print(f"  [ERROR] {m}")
    for m in warns:  print(f"  [WARN ] {m}")
    for m in infos:  print(f"  [INFO ] {m}")
    print(f"----- {len(errors)} error / {len(warns)} warn -----")
    if not errors and not warns: print("  全部通过 ✅")

if __name__ == "__main__":
    main()
