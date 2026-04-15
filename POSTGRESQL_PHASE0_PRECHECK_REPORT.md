# PostgreSQL Phase 0 预验证报告

日期：2026-03-31

适用范围：`cmdb`

本报告记录 `POSTGRESQL_MIGRATION_EXECUTION_PLAN.md` 中 `Phase 0：技术预验证` 的实际执行结果。

## 1. 预检环境

- PostgreSQL：本地已有镜像 `postgres:16.13`
- Redis：本地已有镜像 `redis:8.6.2`
- 持久化策略：不挂载数据卷，使用临时容器 / `tmpfs`
- PostgreSQL 端口：`55432`
- Redis 端口：`56379`
- Flask 预检配置：`cmdb-api/settings_postgresql_phase0.py`

本轮实际使用的数据库容器启动方式：

```bash
docker run -d --rm \
  --name cmdb-pg-phase0 \
  -e POSTGRES_USER=cmdb \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=cmdb \
  -e TZ=Asia/Shanghai \
  -p 55432:5432 \
  --tmpfs /var/lib/postgresql/data:rw \
  postgres:16.13
```

## 2. 已完成验证

### 2.1 连接层

结论：通过

实际结果：

- 使用 `settings_postgresql_phase0.py` 切换到 `postgresql+psycopg2`
- `select 1` 返回 `1`

说明：

- 仅从连接驱动与连接串角度看，应用可成功连接 PostgreSQL
- PostgreSQL 连接本身不是当前阻塞点

### 2.2 空库建表链路

结论：通过

实际执行：

```bash
cd cmdb-api
../.venv_phase0_pg/bin/flask --app 'api.app:create_app("settings_postgresql_phase0")' db-setup
```

说明：

- 在做了最小 PostgreSQL 兼容修正后，`db.create_all()` 可成功创建空库表结构

### 2.3 初始化命令

结论：通过

实际执行：

```bash
cd cmdb-api
../.venv_phase0_pg/bin/flask --app 'api.app:create_app("settings_postgresql_phase0")' cmdb-init-cache
../.venv_phase0_pg/bin/flask --app 'api.app:create_app("settings_postgresql_phase0")' cmdb-init-acl
```

结果：

- `cmdb-init-cache` 执行成功
- `cmdb-init-acl` 执行成功

数据库抽样验证：

- `public` schema 表数量：`80`
- `acl_apps` 数据量：`1`
- `acl_roles` 数据量：`2`

### 2.4 应用 / 启动入口

结论：基本通过

已验证：

- `create_app("settings_postgresql_phase0")` 可启动
- `CMDB_CONFIG_OBJECT=settings_postgresql_phase0` 下，`autoapp` 可导入
- 同样配置下，`celery_worker` 可导入

说明：

- 为支持预检配置对象，`create_app()` 已补充环境变量回退逻辑
- 这说明 API / Celery 启动链路本身没有发现 MySQL 专属强绑定逻辑

## 3. 明确 blocker

### 3.1 现有 Alembic 迁移链不可直接用于 PostgreSQL 空库

结论：失败

实际执行：

```bash
cd cmdb-api
../.venv_phase0_pg/bin/flask --app 'api.app:create_app("settings_postgresql_phase0")' db upgrade
```

失败点：

- 迁移文件 `cmdb-api/migrations/versions/6a4df2623057_.py`
- 在 PostgreSQL 空库上执行时，直接尝试：

```sql
ALTER TABLE c_attributes ADD COLUMN choice_other JSON
```

报错：

- `relation "c_attributes" does not exist`

结论解释：

- 当前迁移链不是“空库从 0 初始化”的 PostgreSQL 基线迁移
- 它隐含依赖既有 MySQL 表结构
- 正式施工不能继续复用这条历史迁移链作为 PostgreSQL 初始建库方案

### 3.2 `flask db current` 存在工具链兼容问题

结论：失败

现象：

- `Flask-Migrate 2.5.2` 调用 `current(head_only=...)`
- 当前 Alembic 组合下报：
  `TypeError: current() got an unexpected keyword argument 'head_only'`

影响：

- 不影响 `db-setup`
- 但说明当前迁移工具链存在额外兼容性风险

### 3.3 自动迁移脚本不能“直接信任”

结论：部分通过，但不能直接作为交付方案

观察结果：

1. 在预修复模型状态下，`stamp head` 后可以生成新的迁移脚本
2. 但生成脚本中出现了 `mysql.DOUBLE(asdecimal=True)`
3. 同时升级执行时触发：
   `PostgreSQL ENUM type requires a name`

这说明：

- Alembic 自动生成“能产出文件”，不等于“能直接 upgrade 成功”
- 自动生成脚本必须人工审核

后续观察：

- 将枚举切为非原生 enum、将 `DOUBLE` 替换为通用浮点后，`stamp head -> db migrate` 又出现了 `alembic_version` 重复创建异常
- 该问题需要单独排查，但已经足以说明：当前 Alembic 流程还不具备“正式施工可直接依赖”的稳定性

## 4. 本轮确认的 PostgreSQL 兼容策略

### 4.1 Enum 策略

当前建议：优先使用 `native_enum=False`

原因：

- 可避免 PostgreSQL 原生 enum 对类型命名的要求
- 可避免不同列重复使用相同 enum type name 的冲突
- 更适合本项目当前“大量历史模型 + 迁移链不干净”的现实情况

本轮已在模型层用 `CompatEnum(..., native_enum=False)` 验证该方向可行。

### 4.2 浮点类型策略

当前建议：移除 MySQL 方言 `DOUBLE`，改为通用 `db.Float(precision=53)`

原因：

- `sqlalchemy.dialects.mysql.DOUBLE` 会污染 PostgreSQL 自动迁移脚本
- 通用浮点类型更适合作为跨数据库基线

## 5. 本轮代码改动

本次为完成 Phase 0 预检，已落下以下最小改动：

- `cmdb-api/settings_postgresql_phase0.py`
  - 增加 PostgreSQL 预检专用配置对象
- `cmdb-api/api/lib/database.py`
  - 增加 `CompatEnum`
- `cmdb-api/api/models/acl.py`
  - 将模型枚举改为 `CompatEnum`
- `cmdb-api/api/models/cmdb.py`
  - 将模型枚举改为 `CompatEnum`
  - 将 MySQL `DOUBLE` 替换为通用浮点
- `cmdb-api/api/views/common_setting/file_manage.py`
  - 将 `python-magic` 改为惰性导入，避免数据库 CLI 被宿主机缺少 `libmagic` 阻断
- `cmdb-api/api/app.py`
  - `create_app()` 支持从 `CMDB_CONFIG_OBJECT` 读取配置对象

## 6. 尚未处理但已确认的后续项

以下问题不影响本轮 Phase 0 已跑通的最小闭环，但必须进入后续施工：

- `cmdb-api/migrations/versions/6a4df2623057_.py` 不能继续作为 PostgreSQL 空库基线迁移
- 需要设计新的 PostgreSQL baseline migration 策略
- `cmdb-api/api/lib/common_setting/utils.py`
  - 仍引用 `sqlalchemy.dialects.mysql.ENUM`
  - 仍使用反引号和 MySQL 风格 `ALTER TABLE ... MODIFY COLUMN`
  - `common-check-new-columns` 尚未做 PostgreSQL 适配
- 原始 SQL 文件 `docs/cmdb.sql` / `docs/cmdb_en.sql` 仍然是 MySQL 初始化脚本，不能用于 PostgreSQL
- Docker / Makefile / 文档里的 MySQL 默认配置仍未正式切换

## 7. Phase 0 结论

### 已确认成立

- 应用可以连接 PostgreSQL
- 在最小兼容修正后，空库可建表
- `cmdb-init-cache` 可执行
- `cmdb-init-acl` 可执行
- API / Celery 启动入口可适配 PostgreSQL 预检配置

### 已确认不成立

- 现有 Alembic 历史迁移链可直接复用于 PostgreSQL 空库
- 自动生成迁移脚本可不经人工审核直接用于 PostgreSQL

## 8. 是否进入正式施工

结论：可以进入下一阶段，但必须按以下前提推进

1. 不复用现有 MySQL 历史迁移链作为 PostgreSQL 空库基线
2. 正式采用“模型兼容修正 + PostgreSQL 基线迁移重建”的路线
3. `common-check-new-columns`、原始 SQL、Docker / 文档中的 MySQL 依赖需在后续阶段继续清理
