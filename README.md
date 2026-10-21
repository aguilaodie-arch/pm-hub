# PM Hub（产品需求工作台）

示例公司产品部内部工具：需求池管理 + AI 预设计 + Axure 原型托管与问答 + 版本归档沉淀知识库 + 知识问答。
内网部署，供 8 名 PM 与 20+ 研发使用。

> 业务规则唯一事实源：`specs/pm-hub/` 八件套（见 `AGENTS.md`）。实现期 Spec 外决策登记在 `specs/pm-hub/decisions.md`。

## 功能

1. **用户中心**：三角色——主账号（admin，唯一，管配置中心与已上线回退）/ 产品经理（pm，全部业务写操作）/ 研发（dev，只读 + 原型问答与反馈）。登录态 7 天。
2. **需求池**：14 字段模型（需求编号 RQ+yyMMdd+4位序列自动写入），六态状态机（待澄清/待设计/设计中/待串讲/研发中/已上线）任意方向手动流转；已上线需求只读，仅主账号可回退"研发中"；删除仅创建人或主账号。
3. **需求材料区**：需求维度附件（单文件 ≤20MB、单需求 ≤20 个、格式白名单），共享可见，供预设计 Agent 引用；材料不进知识库。
4. **需求预设计（Agent-1）**：需求维度多对话，PM 间共享可接力（研发不可见）；挂知识库冷启动 + 内置技能（脑暴/Grill-me/PRD/BDD）；一键导出 `{需求编号}-预设计.md`。
5. **项目/版本/原型**：项目→版本→原型三级。Axure「生成 HTML」文件夹直接整目录上传（也兼容 ZIP）；入口探测 index.html → start.html → 唯一 .html；同名覆盖更新（二次确认），免登直链 `/p/{access_key}/` 保持不变；已归档版本禁止上传/删除原型。
6. **原型问答（Agent-2）**：原型问答页左预览右问答，单发式问答（D22，不留历史会话）；研发可点「未解决 · 找产品经理」——LLM 按 AC 模板生成摘要，钉钉工作通知推送原型上传人（含跳转链接），PM 在问答页原位「标记已处理」闭环。
7. **版本归档**：归档确认弹窗（N 条需求将标记已上线）→ 后台任务逐需求生成结构化知识条目（知识卡：背景与目标/方案要点/业务规则与口径/异常流与边界/涉及页面与联动影响），再汇总版本级索引 → 全部写入内置知识库 → 版本下需求批量置"已上线"并写实际上线日期；进度可轮询、失败可断点重试（D19）。
8. **知识库**：内置 Chroma + 本地 ONNX 向量模型（jina-embeddings-v2-base-zh，decisions.md D1）；唯一写入入口=归档；#/pc/kb 提供「知识浏览」（版本→条目浏览/搜索/查看，PM/主账号可编辑与重新生成，人工编辑的条目重归档不覆盖）+「知识问答」（检索片段带「《标题》（编号）」来源标签）（D19）。
9. **统计分析**：按项目/状态/PM 三维度计数 + PM 工作量表（需求计数，D26 起移除人天口径）。
10. **Jira 联动（D23）**：需求详情页手动「转 Jira」——AI 按模板生成用户故事（含验收标准）写入 Jira 全局目标项目，issueKey 回写关联；失败落"同步失败"可重试，不阻塞需求流转；需求删除时 Jira 侧故事联动废弃（流转完成态+评论，禁止真删除 issue）。
11. **配置中心**（仅主账号，左侧分组竖导航）：LLM 网关（含连通性测试）/ Agent-1 / Agent-2 / 归档摘要模板 / 知识库参数 / 钉钉推送（应用配置 + AC 摘要模板 + 测试推送，D22）/ Jira（连接配置 + 用户故事模板 + 测试连接，D23）/ 账号管理（含钉钉 userid）/ 磁盘用量（≥80% 标红）。

## 快速开始

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp config.example.yaml config.yaml   # 然后编辑 config.yaml，至少填 ai.base_url / ai.api_key
.venv/Scripts/python run.py
# 打开 http://localhost:8000 ，用 admin / admin123 登录（首次登录后请立即修改密码）
```

或双击 `启动.bat`（自动建虚拟环境并装依赖）。

**向量模型（知识库检索需要）**：内置检索使用本地 ONNX 模型 jina-embeddings-v2-base-zh，模型文件不随仓库分发（体积约 160MB）。请从 HuggingFace 下载 `jinaai/jina-embeddings-v2-base-zh`，把仓库文件放到 `models/jina-embeddings-v2-base-zh/`（需要 `tokenizer.json` 与 `onnx/model_quantized.onnx`），路径可在 `config.yaml` 的 `embedding.model_path` 调整。未配置模型时系统仍可运行，仅知识库检索/归档不可用。

**从旧版本升级**：`.venv/Scripts/python migrate_v2.py`（自动备份 app.db 后迁移字段/枚举/对话表）。

**演示数据**：`.venv/Scripts/python seed.py`（导入 specs/pm-hub/05-seed-data.yaml；种子账号初始密码 `pmhub12345`，admin 已存在则密码不变）。

**自检**：`.venv/Scripts/python check_invariants.py`（不变量 I1/I2/I3/I6/I7）；服务运行时可加 `--api http://127.0.0.1:8000` 追加 I8 检查。

## 并发与性能设计

按 40 人产研团队（8 PM + 20+ 研发）同在线的规模设计，重操作全部让出主线程：

- **LLM 问答不阻塞他人**：知识问答 / 原型问答 / 预设计均为同步路由，由 FastAPI 线程池并发执行——一个人等 AI 回答几十秒，其他人操作不受影响
- **原型上传不卡站**：上传的接收走异步 IO，ZIP 解压 / 目录落盘 / 全文提取等 CPU 与磁盘重活经线程池执行（`run_in_threadpool`），大文件上传期间全站流畅
- **归档异步**：版本归档为后台线程任务，进度轮询，不占用请求
- **SQLite WAL 模式**：读写互不阻塞 + 写锁冲突自动等待（busy_timeout 5s），多人同时浏览与录入不互斥
- **列表全分页**：需求池 / 知识浏览每页 20 条，数据量增长不拖慢页面

## 发布原型操作步骤

1. Axure 中「发布 → 生成 HTML 文件」到本地某个文件夹。
2. 平台内「项目与版本」选中版本 →「上传原型」：直接选生成出的文件夹（或拖入），也可先压成 ZIP 再传。
3. 得到免登直链。同名上传会弹窗确认后覆盖更新，链接保持不变。

## 系统配置

管理员进入「配置中心」（#/pc/admin）：LLM 网关 / Agent 提示词与开关 / 归档摘要模板 / 账号管理 / 磁盘用量。
配置写回 `config.yaml`，模型配置立即生效，host/port/路径需重启。

## 目录结构

```
app/
  config.py        配置加载（config.yaml + Settings，D4）
  database.py      SQLAlchemy / SQLite
  models.py        数据模型（对齐 01-domain-model.yaml）
  security.py      密码哈希
  ai.py            LLM 客户端（OpenAI 兼容；主模型 / 预设计 Agent / Agent-2）
  embedder.py      本地 ONNX 向量推理
  extract.py       从 Axure HTML 提取文字/批注
  knowledge.py     Chroma 向量知识库（内置方案，D1）
  dingtalk.py      钉钉工作通知推送（D22：token 缓存/发送/测试）
  jira.py          Jira REST 联动（D23：建 Story/废弃联动/连接测试）
  main.py          路由 + 页面
  templates/       登录页 / 主 SPA（hash 路由 #/pc/...）
specs/pm-hub/      Spec 八件套 + decisions.md + spec_lint.py
migrate_v2.py      旧版数据迁移脚本
seed.py            种子数据导入
check_invariants.py 不变量自检（I1-I8）
axure_plugin/      Axure 插件骨架 + 本地桥接助手
models/            本地向量模型
data/              运行产物（db / chroma / 发布的原型）
```

## 后续内网部署

- 改 `config.yaml` 的 `host`/`port`、`publish_root`；磁盘总量用环境变量 `DISK_TOTAL_BYTES` 注入（默认 500GB）。
- 数据库 SQLite（备份=拷文件）；知识库 Chroma 为本地文件型，随 `data/` 迁移。
- 未来若切换 MaxKB/Ollama 方案，见 `specs/pm-hub/decisions.md` D1。
