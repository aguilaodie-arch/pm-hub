# 不变量与验收断言（机器可检查，实现为系统自检脚本/单元测试）

## I1 引用完整性
- 断言：每条 requirement.projectId、requirement.pmId、requirement.createdBy 存在于 account/project；requirement.versionId 非 null 时存在于 version；每条 version.projectId 存在于 project；每条 material.requirementId 存在于 requirement；每条 prototype.versionId 存在于 version；每条 conversation.requirementId 存在于 requirement；每条 message.conversationId 存在于 conversation；每条 qaLog.prototypeId 存在于 prototype
- 检查：全量外键遍历，空引用/悬挂引用即失败

## I2 归档一致性
- 断言：version.status=已归档 的版本 ⇒ ①version.summary 非空且 version.kbDocId 非空且 version.archivedBy/archivedAt 非空；②其下每条 requirement.status=已上线 且 requirement.actualOnlineDate 非空
- 检查：遍历已归档版本逐条断言

## I3 原型唯一性与落盘完整
- 断言：同一 versionId 下 prototype.name 无重复；每个 prototype.dirPath 指向的目录真实存在，且目录内含 entryPath 声明的入口文件
- 检查：分组查重 + 文件系统探测

## I4 权限边界
- 断言：role=dev 的账号调用任何写接口（新建/编辑/删除需求、上传材料、上传原型、归档、配置）返回 403，仅"提交问答、提交反馈"两个写接口放行；#/pc/admin 的全部接口仅 role=admin 可用
- 检查：以 dev 会话逐个调用写接口断言 403；以 pm 会话调 admin 接口断言 403

## I5 状态-操作一致性
- 断言：页面不出现 02 矩阵中禁用的操作——status=已上线的 requirement 不渲染"编辑/删除/上传材料"入口（不是置灰）；status=已归档的 version 不渲染"上传原型/执行归档"按钮
- 检查：按状态抽查对应页面 DOM/接口可用性

## I6 材料约束
- 断言：每条 material.size ≤ 20971520（20MB）且 material.mime 属于白名单（png/jpg/jpeg/gif/webp/pdf/doc/docx/xls/xlsx/csv/ppt/pptx/md/txt 对应 MIME）；同一 requirementId 下 material 条数 ≤ 20
- 检查：全量遍历断言 + 上传接口构造越界请求断言被拒绝

## I7 枚举合法性
- 断言：requirement.status ∈ {待澄清, 待设计, 设计中, 待串讲, 研发中, 已上线}；version.status ∈ {进行中, 已归档}；qaLog.feedback ∈ {未反馈, 已解决, 未解决}（D17 起新记录恒为"未反馈"，历史值保留）；account.role ∈ {admin, pm, dev}
- 检查：全表扫描，越界值即失败

## I8 免登边界
- 断言：未登录状态访问 /p/{prototypeId}/ 返回 200 且页面不含任何问答/工具条元素；未登录访问其余任意页面跳转 #/pc/login、调用任意 API 返回 401
- 检查：无会话请求逐路径断言
