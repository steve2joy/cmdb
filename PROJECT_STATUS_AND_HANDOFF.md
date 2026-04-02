# 项目状态与线程交接记录

> 适用仓库：`cmdb`  
> 当前主线分支：`v2.5.5-pgdb`  
> 最近整理日期：`2026-04-02`  
> 用途：给后续切线程、继续施工、排障和回归测试提供统一背景，不再依赖聊天上下文恢复现场。

---

## 1. 项目背景

本项目是 `veops/cmdb` `v2.5.5` 的 PostgreSQL 化改造分支，目标不是“兼容双库”，而是把默认主库从 MySQL 切到 PostgreSQL 16。

当前已明确的边界：

- 本次改造面向 **新项目 / 空库启动**
- 不做历史 MySQL 存量数据迁移
- 不做双写、灰度切流、回滚切流
- Redis / Celery / UI 技术栈保持不变
- 项目默认按 **纯净模式** 安装

“纯净模式”的含义：

- 初始化数据库结构
- 初始化 ACL
- 初始化管理员账号
- 不自动导入任何 CMDB 模型模板或业务数据
- 模型模板由登录后人工按需导入

---

## 2. 已确认的关键决策

### 2.1 数据库与迁移策略

- PostgreSQL 目标版本：`16`
- 本地验证镜像：`postgres:16.13`
- 不复用旧 MySQL Alembic 历史迁移链
- PostgreSQL 空库基线迁移已重建为：
  `cmdb-api/migrations/versions/202603310001_postgresql_baseline.py`
- Enum 走 `native_enum=False` 路线

### 2.2 安装与初始化策略

- 默认安装模式为“纯净模式”
- 不再从 `docs/cmdb.sql` 自动导入模型或业务数据
- `docs/cmdb.sql` 只作为历史参考，不再作为 PostgreSQL 初始化入口
- 管理员账号通过应用层命令 `flask ensure-bootstrap-admin` 幂等补齐

### 2.3 管理员账号策略

- 当前默认 bootstrap 管理员：
  - 用户名：`admin`
  - 默认密码：`123456`
- 相关配置：
  - `BOOTSTRAP_ADMIN_ENABLED`
  - `BOOTSTRAP_ADMIN_USERNAME`
  - `BOOTSTRAP_ADMIN_PASSWORD`
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_RESET_PASSWORD`
- 生产环境必须覆盖 `BOOTSTRAP_ADMIN_PASSWORD`

说明：

- 目前仓库里已经有 bootstrap admin 机制
- “生产环境未配置 `BOOTSTRAP_ADMIN_PASSWORD` 就拒绝初始化”的强保护 **尚未实现**
- 如果后续继续收口安全策略，这是仍可继续推进的一项待办

### 2.4 前端模板导入策略

- 项目默认不自动 seed 模型模板
- 模型模板由用户登录后，从模板市场下载并通过系统导入
- 当前路径符合官方“纯净模式安装”思路

---

## 3. 当前运行态快照

以下快照基于 `2026-04-02` 当前工作机上的实际环境：

- `cmdb-db`：运行中，镜像 `postgres:16.13`
- `cmdb-cache`：运行中
- `cmdb-api`：运行中，健康检查通过
- `cmdb-ui`：运行中，对外端口 `8000`

当前入口：

- UI：`http://127.0.0.1:8000`
- PostgreSQL：`127.0.0.1:25432`

当前已验证可用：

- `GET /` 返回 `200`
- `POST /api/v1/acl/login` 返回 `200`
- `admin / 123456` 可以登录

---

## 4. 已完成的大阶段

### 4.1 PostgreSQL 迁移主线

已完成：

- Phase 0：技术预验证
- Phase 1：依赖、配置、Docker 切换
- Phase 2：模型层与 PostgreSQL baseline migration 重建
- Phase 3：原始 SQL / 查询兼容改造
- Phase 4：初始化链路与运行链路验证
- Phase 5：第一轮测试与回归

主线结论：

- PostgreSQL 已成为默认主库
- 默认 compose 启动链可工作
- 项目已达到“可运行、可登录、可初始化、可进行核心人工验证”的状态
- 自动化覆盖仍不足，整体仍属于 **B 级验收 + 持续补坑阶段**

### 4.2 PostgreSQL 兼容性修复

除主线 Phase 0-5 外，后续又补了几轮运行态缺陷修复，主要包括：

- 隐式类型转换问题集中治理
- CMDB cache 中 `id/name/alias` 查询歧义修复
- 拓扑视图 `DISTINCT + ORDER BY` PostgreSQL 兼容修复
- 混合类型值表 `UNION` 的 `text/json/int/float/datetime` 兼容修复
- CIType 继承查询里字符串模型名与整型 `child_id` 混用修复
- 资源层级前端“新增应用无响应”原版 bug 修复

---

## 5. 关键问题与处理结论

### 5.1 MySQL 隐式类型转换问题

这是本项目 PostgreSQL 迁移后暴露最集中的一类问题。

根因：

- 视图层把原始 `request.values` 直接喂给 ORM
- 通用 helper 直接用 `column == value`
- 布尔开关依赖 Python truthy
- 员工筛选会生成 `integer = ''` / `integer != ''`
- MySQL 容忍字符串/整型/布尔的宽松比较，PostgreSQL 不容忍

已修复范围：

- 共享查询 helper
- ACL
- common-setting
- CMDB history / preference
- CMDB ci_type / relation
- auto discovery

文档索引：

- `POSTGRESQL_IMPLICIT_TYPE_FIXLIST.md`

### 5.2 模板导入报错：`c_attributes.name = 19`

根因：

- `AttributeCache.get(19)`、`CITypeCache.get(19)` 一类调用会先按 `name=19` 查，再按 `id=19` 查
- PostgreSQL 对 `varchar = integer` 直接报错

处理结果：

- cache 层改为整数 key 优先按 `id` 查，再兜底 `name/alias`

### 5.3 拓扑视图中心节点实例搜索报错

根因：

- `SELECT DISTINCT ci_id ... ORDER BY c_cis.type_id`
- PostgreSQL 要求 `ORDER BY` 字段必须出现在 `SELECT DISTINCT` 结果中

处理结果：

- 排序值改为一并进入子查询，再由外层排序

### 5.4 创建物理机后报错但数据已落库

根因：

- 创建成功后，回读 SQL 将不同类型的 `value` 直接 `UNION`
- PostgreSQL 不接受 `text` 与 `json` 直接 `UNION`

处理结果：

- 回读 SQL 中统一 `CAST(value AS TEXT)`，再由 Python 按 `value_type` 反序列化

### 5.5 资源层级新增应用无响应

结论：

- 这不是 PostgreSQL 引起的后端问题
- 是原版前端树视图页面的 bug

根因：

- 表单提交前会访问缺失字段配置，直接触发 `undefined.is_reference`
- 校验失败分支存在静默返回
- 表格 ref 时序访问缺少判空

处理结果：

- 安全跳过未知字段
- 校验失败给出明确提示
- 树视图页统一补 ref 判空

---

## 6. 测试与验证结果汇总

### 6.1 已完成的命令/服务验证

已验证通过的主线命令：

- `flask db upgrade`
- `flask db current`
- `flask cmdb-init-cache`
- `flask cmdb-init-acl`
- `flask init-import-user-from-acl`
- `flask init-department`
- `flask ensure-bootstrap-admin`

已验证通过的运行链路：

- Gunicorn 可启动
- Celery worker 可启动
- `docker compose up -d --build` 闭环可运行
- `cmdb-api` 健康检查通过
- `cmdb-ui` 对外入口可访问

### 6.2 已完成的自动化 / 半自动验证

- `pytest tests/ -v --tb=short`
  - 当前仓库实际仅收集到 `1` 条真实测试并通过
- `python3 -m py_compile`
  - 已多次用于后端 Python 文件静态校验

说明：

- 前端 `.vue` 文件不能用 `py_compile`
- 当前前端验证仍以构建 + 浏览器 smoke test 为主

### 6.3 已完成的接口/浏览器验证

后端/接口层已验证通过的代表性能力：

- 登录
- `ci_types` 查询
- `relation_types` 查询
- `attributes/search`
- CI 搜索
- `common-check-new-columns`
- auto discovery 查询
- ACL 资源组查询
- 模板导入/导出
- 拓扑视图中心节点实例搜索

浏览器/手工验证已确认通过的代表性场景：

- `admin / 123456` 登录
- 模型配置中的模板导入
- 资源数据中创建物理机
- 资源层级中新增应用
- 拓扑视图中新建拓扑时搜索中心节点实例

说明：

- 以上最后三类结果包含人工验证结论
- 自动化覆盖仍不充分，不应误判为“全量业务回归完成”

---

## 7. 前端构建与发布注意事项

这是当前最容易在换线程后再次踩坑的一条，必须单独记录。

### 7.1 根因

仓库中的：

- `cmdb-ui/.env`

默认包含：

- `VUE_APP_API_BASE_URL=http://127.0.0.1:5000/api`

而正式 Docker 构建时，`docker/Dockerfile-UI` 会先执行：

- `sed -i "s#http://127.0.0.1:5000##g" .env`

也就是把前端 API 基址改成相对路径 `/api`。

### 7.2 风险

如果直接在源码目录或临时目录执行：

- `npm run build`
- `yarn build`

但没有先把 `.env` 里的 `VUE_APP_API_BASE_URL` 改成 `/api`，前端会把接口地址编译成：

- `http://127.0.0.1:5000/api`

浏览器就会绕过 `8000` 的 Nginx 代理，直接打 `5000`，表现为：

- 登录 `403`
- 页面能打开但接口异常

### 7.3 正确做法

本地手工构建 UI 时，必须满足以下任一条件：

1. 直接走 `docker/Dockerfile-UI`
2. 手工把构建环境中的 `VUE_APP_API_BASE_URL` 改成 `/api`
3. 确认最终产物中不再包含 `127.0.0.1:5000`

### 7.4 当前运行环境的临时兼容处理

为避免浏览器缓存旧 bundle hash 导致白屏，当前运行中的 `cmdb-ui` 容器里额外补了几条旧 hash 兼容别名。

注意：

- 这是 **运行态补丁**
- 不是源码中的正式产物
- 容器重建后如果再次出现旧缓存白屏，需要重新清缓存或重新补兼容别名

---

## 8. 当前已知限制与未完成项

### 8.1 测试覆盖不足

- 仓库自动化测试样本极少
- 目前不能宣称达到 A 级验收
- 仍建议补更多创建/更新/删除路径测试

### 8.2 安全策略可继续收口

- bootstrap admin 默认密码仍存在默认值
- 尚未实现“生产未配置密码则拒绝初始化”的硬保护

### 8.3 纯净模式下业务模型默认为空

这是设计结论，不是 bug。

现状：

- 不自动导入模型模板
- “我的订阅”为空通常意味着当前库没有导入任何 CI 模型或尚未订阅

需要业务模型时：

- 登录系统
- 从模板市场下载模板
- 在系统中手工导入

---

## 9. 建议后续工作顺序

如果下一线程继续推进，建议顺序如下：

1. 补浏览器级回归清单，覆盖更多写路径
2. 收口 bootstrap admin 的生产安全策略
3. 补前端构建发布流程文档，避免再踩 `127.0.0.1:5000` 的坑
4. 视需要补自动化测试，优先覆盖：
   - 登录
   - 模板导入
   - CI 创建/查询
   - 资源层级创建
   - 拓扑视图中心实例搜索

---

## 10. 关联文档

优先阅读顺序建议：

1. `PROJECT_STATUS_AND_HANDOFF.md`
2. `POSTGRESQL_MIGRATION_EXECUTION_PLAN.md`
3. `POSTGRESQL_IMPLICIT_TYPE_FIXLIST.md`
4. `POSTGRESQL_PHASE0_PRECHECK_REPORT.md`

---

## 11. 一句话交接结论

当前分支已经把 PostgreSQL 主线迁移、隐式类型集中治理、模板导入/拓扑/资源层级等关键运行态问题基本打通；系统处于“可运行、可登录、可继续手工回归”的状态，但自动化覆盖仍弱，后续应继续补测试和收口生产安全策略。
