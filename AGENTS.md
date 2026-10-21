# AGENTS.md — PM Hub（产品需求工作台）

> 本文件是 AI Coding（Kimi Code / 任意 Agent）的入口文件。开工前必读，并严格按其执行。

## 项目一句话

示例公司产品部内部工具：需求池管理 + AI 预设计 + Axure 原型托管与问答 + 版本归档沉淀知识库 + 知识问答。内网部署，8 名 PM + 20+ 研发使用，一名 PM 业余时间维护。

## 唯一事实源（SSOT）

全部业务规则以 `specs/pm-hub/` 八件套为准，阅读顺序：

1. `specs/pm-hub/00-overview.md` — 背景/范围/角色/术语命名表/技术拓扑/假设清单
2. `specs/pm-hub/01-domain-model.yaml` — 实体×字段×枚举×默认值（数据层唯一依据）
3. `specs/pm-hub/02-state-machines.md` — 状态机与状态×操作矩阵（按钮可用性照此实现）
4. `specs/pm-hub/03-calculations.md` — 统计与磁盘口径
5. `specs/pm-hub/04-pages.md` — 页面清单+逐操作规约+外部集成契约
6. `specs/pm-hub/05-seed-data.yaml` — 种子数据（`python seed.py` 可导入）
7. `specs/pm-hub/06-invariants.md` — 不变量断言（实现为 `check_invariants.py`）
8. `specs/pm-hub/07-story.md` — 叙事验收路径（完成后按此自测）
9. `specs/pm-hub/decisions.md` — 实现期 Spec 外决策登记处（含已批准的偏离 D1-D7，务必先读）

## 零业务决策原则（最高优先级）

- 字段含义、枚举值、编号规则、状态流转、校验规则、文案，一律以 Spec 为出处。**禁止**自行"优化"、"统一"、"补全"任何业务口径
- 特别警惕 00-overview 中的**反直觉约定**（①状态任意互转 ②原型同名覆盖无版本史 ③材料不进知识库 ④预设计对话对研发不可见 ⑤检索配置不在本系统）——这些是反复拍板的结果，改掉就是 bug
- 遇到 Spec 没写的业务问题：**不要自行决定**。把问题、你的建议方案、影响面记入 `specs/pm-hub/decisions.md`（状态=待审批），并在当次回复中显式报告，等产品负责人批复后再实现
- 技术实现（代码结构、库选型、CSS 写法）不受此限，可自主决策，但须遵守下面的技术约束

## 技术约束（已定决策，不得变更）

- 单体 Web 应用（FastAPI + Jinja2 模板 + 原生 JS，前后端同仓库）+ SQLite + 文件系统存原型与材料
- 知识库为**内置实现**（Chroma + 本地 ONNX embedding，见 decisions.md D1：暂不引入 MaxKB/Ollama）；材料绝不进知识库，知识库唯一写入入口=归档摘要
- 全部 LLM 调用读 `config.yaml` 的 ai.* / design_agent.* 配置（base_url/api_key/model），**禁止硬编码**任何模型地址、密钥
- 免登直链 `/p/{access_key}/` 为纯静态服务，禁止注入任何工具条/问答代码（D2）
- 全部页面 PC Web，hash 路由（#/pc/...），无移动端适配
- 部署目标：内网服务器

## 完成标准（每次交付前自检）

1. `python check_invariants.py` 不变量全部通过
2. 按 07-story 的 10 步路径完整走一遍，每步"预期看到"与实际一致
3. `python specs/pm-hub/spec_lint.py specs/pm-hub/` 无 error
4. decisions.md 中无"待审批"项被擅自实现

## 沟通约定

- 回复用中文
- 发现 Spec 内部矛盾时，停止实现，在回复中指出矛盾点并给出建议取舍，等批复
