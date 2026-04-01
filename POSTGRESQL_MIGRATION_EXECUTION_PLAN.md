# 维易CMDB MySQL → PostgreSQL 16 迁移可施工方案

> 适用范围：当前仓库 `cmdb`  
> 项目版本：v2.5.5  
> 场景前提：**新项目 / 空库启动 / 无存量数据迁移需求**  
> 文档目的：替代此前分散的 4 份分析文档，形成一份**可直接执行**的 PostgreSQL 改造施工方案  
> 修订日期：2026-03-31

---

## 一、文档结论

### 1.1 最终判断

本项目从 MySQL 改造为 PostgreSQL 16 **可以继续执行**，且在“新项目、无存量数据”的前提下，整体风险**可控**。

但本次改造不建议直接按照原先拆解机械执行，原因如下：

1. 原有文档对 **Enum 改造** 的判断过于绝对
2. 对 **Alembic 自动迁移脚本** 的成功率预期偏乐观
3. 对 **原始 SQL、初始化链路、Docker 启动链路** 的检查不够完整
4. 缺少一个正式施工前的 **技术预验证阶段（Phase 0）**

因此，本方案采用如下策略：

- 先做 **0.5~1 天的技术预验证**
- 再进行配置、模型、SQL、迁移脚本与启动链路改造
- 最终以 **空库初始化成功 + 核心 API 冒烟通过 + 测试通过** 为交付标准

---

## 二、适用前提与边界

## 2.1 适用前提

本方案成立的关键前提如下：

- 当前项目是 **新项目**
- **没有历史 MySQL 生产数据**需要迁移
- 不需要做双写、增量同步、回滚切流
- PostgreSQL 将作为新的唯一主库
- Redis / Celery / UI 保持现有技术栈不变

## 2.2 不在本次范围内的内容

以下内容**不纳入本次施工范围**：

- 存量数据从 MySQL 到 PostgreSQL 的迁移
- 双库并行、双写、灰度切流
- 生产回滚演练
- 大规模性能压测与专项调优
- PostgreSQL 高可用部署架构设计

---

## 三、总体实施策略

## 3.1 核心思路

本次改造按“**先验证、后施工、再回归**”的方式推进。

### 实施原则

1. **先验证关键假设，再大面积修改代码**
2. **尽量复用 SQLAlchemy 抽象，不做过度 PostgreSQL 方言化**
3. **优先解决空库可初始化问题**
4. **以最小闭环验证成功为第一阶段目标**
5. **所有结论以实际运行结果为准，不以静态推断替代验证**

---

## 四、工期评估

## 4.1 现实工期

结合当前项目结构、迁移范围与无存量数据前提，建议工期如下：

| 阶段 | 预计工期 |
|------|---------|
| Phase 0 技术预验证 | 0.5 ~ 1 天 |
| Phase 1 配置与依赖改造 | 0.5 天 |
| Phase 2 模型与迁移层改造 | 1 ~ 2 天 |
| Phase 3 原始 SQL 与查询适配 | 0.5 ~ 1.5 天 |
| Phase 4 初始化与运行链路验证 | 0.5 天 |
| Phase 5 测试与回归 | 1 ~ 2 天 |
| **总计** | **4 ~ 7 人天** |

### 4.2 风险上浮后的工期

如果出现以下情况，工期可能上浮到 **6 ~ 8 人天**：

- 枚举类型比预期复杂
- Alembic 自动生成脚本不可直接使用
- 原始 SQL 存在较多 MySQL 专属写法
- 初始化命令与启动脚本中存在硬编码 MySQL 逻辑

---

## 五、施工总路线图

```text
Phase 0  技术预验证
   ↓
Phase 1  依赖/配置/Docker 改造
   ↓
Phase 2  模型层与迁移脚本改造
   ↓
Phase 3  原始 SQL / 查询兼容性改造
   ↓
Phase 4  初始化链路 / 服务启动验证
   ↓
Phase 5  单测 / 冒烟 / 回归验证
   ↓
交付
```

---

## 六、Phase 0：技术预验证（已完成）

> 状态：已于 2026-03-31 完成。  
> 详细记录见 `POSTGRESQL_PHASE0_PRECHECK_REPORT.md`。

## 6.1 已确认成立

本轮预验证已经确认以下假设成立：

1. 仅替换驱动与连接串后，应用可以连接 PostgreSQL
2. 在完成最小兼容修正后，`flask db-setup` 可在 PostgreSQL 空库成功建表
3. `flask cmdb-init-cache` 可执行
4. `flask cmdb-init-acl` 可执行
5. API / Celery 启动入口本身不依赖 MySQL 特定逻辑

## 6.2 已确认不成立

本轮预验证已经确认以下原假设不成立：

1. 现有 Alembic 历史迁移链可直接用于 PostgreSQL 空库
2. 自动生成迁移脚本可不经人工审核直接用于 PostgreSQL
3. 继续保留当前 `db.Enum(...)` 的默认原生行为是稳妥方案

## 6.3 对后续施工的直接约束

Phase 0 结束后，后续阶段必须遵守以下约束：

1. **不再复用现有 MySQL 历史迁移链作为 PostgreSQL 空库基线**
2. **Enum 默认采用 `native_enum=False` 路线**
3. **MySQL 方言 `DOUBLE` 统一替换为通用浮点类型**
4. **`flask db-setup` 仅作为预验证/开发期空库验证手段，正式交付仍需新的 PostgreSQL baseline migration**
5. **`common-check-new-columns`、原始 SQL、Docker / 文档中的 MySQL 依赖仍需继续清理**

---

## 七、Phase 1：依赖、配置与 Docker 改造（已完成）

> 状态：已于 2026-03-31 完成。  
> 完成结果：默认运行链路已切换为 PostgreSQL + Redis，Docker / Makefile / install.sh / README 默认入口不再依赖 MySQL。

## 7.1 改造目标

完成 PostgreSQL 基础接入，使项目的运行配置不再依赖 MySQL。

## 7.2 涉及文件

- `cmdb-api/requirements.txt`
- `cmdb-api/settings.example.py`
- `cmdb-api/.env`
- `cmdb-api/api/app.py`
- 根目录 `.env`
- `docker-compose.yml`
- `Makefile` / `install.sh` / 文档中所有可能引用 MySQL 的地方

## 7.3 具体任务

### 已完成事项

- 已将数据库驱动从 `PyMySQL` 切换为 `psycopg2-binary`
- 已将默认连接变量切换为 `PG_*`
- 已将 `docker-compose.yml` 中的数据库服务切换为 `postgres:16.13`
- 已移除默认启动链路中的 `common-check-new-columns`
- 已同步修正文档、本地开发说明、Makefile 与安装脚本中的 MySQL 默认路径

### 任务 1.1：替换数据库驱动

建议修改：

```diff
- PyMySQL==1.1.0
+ psycopg2-binary==2.9.10
```

> 说明：若项目后续考虑生产环境更严格控制，也可以评估 `psycopg2` 非 binary 包，但当前施工阶段使用 `psycopg2-binary` 更高效。

### 任务 1.2：更新数据库连接配置

推荐采用 PostgreSQL 专用配置变量：

```python
PG_USER = env.str('PG_USER', default='cmdb')
PG_PASSWORD = env.str('PG_PASSWORD', default='123456')
PG_HOST = env.str('PG_HOST', default='127.0.0.1')
PG_PORT = env.int('PG_PORT', default=5432)
PG_DATABASE = env.str('PG_DATABASE', default='cmdb')

SQLALCHEMY_DATABASE_URI = (
    f'postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}'
)
```

建议保留连接池设置：

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_recycle': 300,
    'pool_size': 10,
    'max_overflow': 20,
}
```

如需提高稳定性，可追加：

```python
'connect_args': {
    'connect_timeout': 10,
    'options': '-c timezone=Asia/Shanghai'
}
```

### 任务 1.3：更新 Docker Compose

必须完成以下检查：

- MySQL 服务替换为 PostgreSQL 服务
- 数据卷路径改为 PostgreSQL 的数据目录
- healthcheck 改为 `pg_isready`
- API 服务中的环境变量引用切换为 `PG_*`
- 所有依赖 `cmdb-db` 的服务等待逻辑正确
- 不再挂载 MySQL 初始化 SQL 或 MySQL 配置文件

### 任务 1.4：同步修正文档与脚本
除源码外，必须同步检查：

- `README.md`
- `docs/`
- `Makefile`
- `install.sh`
- 可能存在的部署说明

避免后续执行人员继续被旧的 MySQL 初始化方式误导。

---

## 八、Phase 2：模型层与迁移层改造（已完成）

> 状态：已于 2026-03-31 完成。  
> 完成结果：模型层已切到稳定的 `CompatEnum` / `native_enum=False` 路线，新的 PostgreSQL baseline migration 已重建为 `202603310001_postgresql_baseline.py`，`upgrade/current` 与空库重建验证通过。

## 8.1 改造原则

Phase 0 之后，这一阶段不再以“继续试探是否保留现状”为目标，而应按已验证方向推进。  
建议遵循以下优先级：

1. **能用标准 SQLAlchemy 类型解决的，优先用标准类型**
2. **枚举默认采用 `native_enum=False`，避免 PostgreSQL 原生 enum 类型管理复杂度**
3. **MySQL 方言类型优先改为跨数据库通用类型**
4. **不复用现有 MySQL 历史迁移链，改为重建 PostgreSQL baseline migration**
5. **Alembic 生成脚本必须人工审查**

### 已完成事项

- 已用通用浮点类型替换 MySQL `DOUBLE`
- 已将枚举输出稳定化，避免 `BaseEnum.all()` 因无序集合导致迁移内容抖动
- 已删除旧 MySQL baseline migration `6a4df2623057_.py`
- 已重建 PostgreSQL baseline migration：`cmdb-api/migrations/versions/202603310001_postgresql_baseline.py`
- 已补充 Alembic `current` 的兼容修正，避免 `head_only` 参数导致命令报错
- 已完成两次空库 `upgrade` 验证，并通过 `cmdb-init-cache` / `cmdb-init-acl` 验证

---

## 8.2 DOUBLE 类型改造

### 识别点
当前文档识别出 `api/models/cmdb.py` 中存在 MySQL 方言：

```python
from sqlalchemy.dialects.mysql import DOUBLE
```

### 推荐改造方式

```python
from sqlalchemy import Float
```

字段可优先改为：

```python
db.Column(Float(precision=53), nullable=False)
```

### 注意事项

若字段涉及以下场景，需要额外确认：

- 精度敏感比较
- 唯一约束
- 排序稳定性
- 聚合统计

如果仅用于普通浮点值存储，则该改法可接受。

---

## 8.3 Enum 改造策略（根据 Phase 0 结论修订）

## 8.3.1 已定策略

Phase 0 已验证：当前项目不应继续尝试“保持现状 + 依赖 PostgreSQL 原生 enum 自动处理”的路线。  
正式施工默认采用：

- 模型层统一使用 `native_enum=False`
- 如需封装，统一使用兼容层（例如 `CompatEnum`）
- 不将 `postgresql.ENUM` 作为默认方案

## 8.3.2 采用该策略的原因

Phase 0 已暴露以下问题：

- PostgreSQL 原生 enum 要求显式类型名
- 多个字段复用 enum 时容易出现类型命名和复用冲突
- Alembic 自动生成和执行链路稳定性不足

因此，本次施工应优先选择**非原生 enum**，把类型约束控制在 SQLAlchemy / 应用层，而不是 PostgreSQL 类型系统。

## 8.3.3 仅保留的例外情况

只有当后续确实存在强数据库约束需求，且已经能够稳定管理：

- 显式 enum type name
- enum 生命周期
- 迁移脚本升级/回滚

才考虑单独引入 PostgreSQL 原生 enum。  
该路线**不属于当前默认施工方案**。

---

## 8.4 除 DOUBLE / Enum 外必须补充检查的模型层事项

以下内容原文档覆盖不完整，本方案新增为强制检查项：

### 8.4.1 Boolean 语义
检查是否存在：

- 原始 SQL 中 `= 1 / = 0`
- 默认值写法依赖 MySQL
- 模型字段与查询条件不一致

### 8.4.2 JSON 字段
检查是否仅做存储，还是还做查询。

若仅存储，继续使用 `db.JSON` 即可。  
若有复杂查询，需要重点验证 PostgreSQL JSON/JSONB 语义。

### 8.4.3 DateTime / 时区
检查：

- 默认值
- 时区处理方式
- 数据库层 `server_default`
- 时间比较与排序逻辑

### 8.4.4 自增主键 / 序列
检查 PostgreSQL 下的：

- 自增行为
- 序列生成
- 主键默认值
- 初始化后 sequence 是否正常

### 8.4.5 索引与唯一约束
重点检查：

- 大小写敏感差异
- 唯一索引语义差异
- 组合索引生成是否正常

---

## 8.5 Alembic 与基线迁移策略

## 8.5.1 现有历史迁移链不适用

Phase 0 已确认：

- 当前 `cmdb-api/migrations/versions/6a4df2623057_.py` 不能作为 PostgreSQL 空库 baseline migration
- 其执行过程隐含依赖既有 MySQL 表结构

因此，正式施工必须**放弃直接复用当前历史迁移链**。

## 8.5.2 正式施工路线

建议采用以下路线：

1. 先完成模型层 PostgreSQL 兼容修正
2. 在兼容后的模型基础上，重建 PostgreSQL baseline migration
3. 新的 baseline migration 只面向“空库从 0 初始化”
4. 历史 MySQL 迁移文件仅作为参考，不再作为 PostgreSQL 初始化依据

## 8.5.3 自动生成脚本的定位

Alembic 自动生成只可作为**辅助起草工具**，不能直接视为最终交付物。  
所有自动生成脚本必须人工审核以下内容：

- enum 定义
- 浮点类型
- 索引
- 唯一约束
- foreign key
- server default
- JSON 字段
- 布尔默认值
- 时间字段默认值

## 8.5.4 验证标准

新的 PostgreSQL baseline migration 至少要在**空库**上验证以下两次：

1. `upgrade` 成功
2. 删除数据库后重新建空库再次 `upgrade` 成功
3. 随后 `cmdb-init-cache` 与 `cmdb-init-acl` 成功

---

## 九、Phase 3：原始 SQL 与查询兼容性改造

> 完成结果：查询层与原始 SQL 中已确认的 MySQL 方言已完成第一轮清理，`common-check-new-columns` 已适配 PostgreSQL，关键搜索 SQL 与 ACL 正则匹配已在临时 PostgreSQL 16 / Redis 环境完成执行验证。

## 9.1 涉及位置

重点检查以下文件：

- `cmdb-api/api/lib/cmdb/query_sql.py`
- `cmdb-api/api/lib/cmdb/search/ci/db/query_sql.py`
- `cmdb-api/api/lib/cmdb/search/ci/db/search.py`
- `cmdb-api/api/lib/cmdb/ci.py`
- `cmdb-api/api/lib/common_setting/utils.py`
- `cmdb-api/api/lib/database.py`
- `cmdb-api/api/tasks/acl.py`
- `cmdb-api/api/lib/perm/acl/trigger.py`
- `docs/cmdb.sql`
- `docs/cmdb_en.sql`

如有需要，继续扩展搜索：

- `search/`
- `tasks/`
- `lib/`
- `views/`

其中需要特别说明：

- `docs/cmdb.sql` / `docs/cmdb_en.sql` 是 MySQL 初始化脚本，**不再适合作为 PostgreSQL 初始化路径**
- `common-check-new-columns` 已完成第一轮 PostgreSQL 适配，不再依赖 MySQL `ENUM` / 反引号 / `CREATE INDEX` 拼串

## 9.1.1 本轮已完成的修正

- 去除查询模板中的 MySQL 反引号与双引号字符串字面量
- 将 `SQL_CALC_FOUND_ROWS` / `FOUND_ROWS()` 改为 PostgreSQL 可执行的 `COUNT(DISTINCT ...)`
- 将 `LIMIT offset, count` 改为 `LIMIT count OFFSET offset`
- 将原始 SQL 中的文本匹配统一收敛为 `ILIKE`
- 对整数 / 浮点 / 日期时间值搜索增加 `CAST(... AS TEXT)`，避免 PostgreSQL 上对非文本列直接 `LIKE`
- 将 `regexp` 运算符切换为按方言选择：PostgreSQL 使用 `~`
- 将 `db.session.execute(query_sql)` 的裸字符串执行改为 `text(query_sql)`
- 将 `common-check-new-columns` 改为基于 SQLAlchemy 方言编译列定义与索引创建

## 9.1.2 本轮执行验证

已在临时环境完成以下验证：

- `flask db upgrade`
- `flask db current`
- `flask cmdb-init-cache`
- `flask cmdb-init-acl`
- `flask common-check-new-columns`
- 最小化业务数据下的 Search 执行验证：
  - 文本属性搜索
  - 数值属性模糊搜索
  - 无属性自由搜索
  - 无属性列表搜索
  - `~attr:*` 缺失属性搜索
- ACL 资源名正则匹配在 PostgreSQL 下执行成功

---

## 9.2 原始 SQL 必查项

原文档只强调了反引号与字符串引号，这还不够。  
本方案要求至少检查以下内容：

### 9.2.1 标识符引用
- MySQL 反引号 `` ` ``
- PostgreSQL 双引号 `"`

若不是保留字，优先考虑**直接去掉引用**，降低跨数据库复杂度。

### 9.2.2 字符串字面量
必须使用单引号 `'...'`，避免混用双引号。

### 9.2.3 MySQL 函数
重点搜索：

- `ifnull`
- `group_concat`
- `find_in_set`
- `date_format`
- `regexp`
- `concat`
- `unix_timestamp`
- `from_unixtime`

逐项确认 PostgreSQL 替代方案：

- `ifnull` → `coalesce`
- `group_concat` → `string_agg`
- 其他函数按实际语义重写

### 9.2.4 LIKE / ILIKE / 大小写
- ORM 层 `ilike()` 一般无需改
- 原始 SQL 中手写 `LIKE` 需确认是否需要改成 `ILIKE`
- 同时确认索引是否仍然可用

### 9.2.5 分页 / 排序 / 布尔表达式
检查：

- `limit`
- `offset`
- `order by`
- `is null`
- `= true / false`
- 布尔列与整型比较混用

---

## 十、Phase 4：初始化链路与运行链路验证（已完成）

> 状态：已于 2026-04-01 完成。  
> 完成结果：PostgreSQL 默认初始化命令链、Gunicorn、Celery 与 `docker compose up -d --build` 整链路验证通过，默认启动脚本中暴露出的 PostgreSQL 类型兼容问题已完成修正。

## 10.1 验证目标

保证项目不只是“能建表”，而是“能启动、能初始化、能跑核心流程”。

## 10.2 重点验证项

### 10.2.1 初始化命令
本轮已完成验证：

```bash
flask db upgrade
flask db current
flask cmdb-init-cache
flask cmdb-init-acl
flask init-import-user-from-acl
flask init-department
```

说明：

- Phase 2 完成后，正式默认链路已切换为 `flask db upgrade`
- `db-setup` 不再作为 PostgreSQL 正式交付路径
- 上述命令已在临时 PostgreSQL 16.13 / Redis 环境与 `docker compose` 默认启动链中完成验证

### 10.2.2 API 服务启动
本轮已完成验证：

- Flask / Gunicorn 正常启动
- 能连接 PostgreSQL
- 不再引用 MySQL 环境变量
- 不存在启动时数据库初始化脚本失败
- 本地 `gunicorn --workers=1 autoapp:app` 启动成功
- `docker compose` 下 `cmdb-api` 健康检查通过

### 10.2.3 Celery Worker 启动
本轮已完成验证：

- Worker 正常启动
- 不因数据库连接配置变化失败
- 与 Redis / PostgreSQL 都能正常工作
- 已在临时环境验证 `one_cmdb_async` / `acl_async` 双队列 worker ready
- `docker compose` 下两个 Celery worker 进程正常驻留于 `cmdb-api` 容器内

### 10.2.4 Docker 启动闭环
本轮已完成验证：

- PostgreSQL ready
- Redis ready
- API ready
- UI ready
- Celery ready（如当前部署方式启用）
- `curl http://127.0.0.1:8000/` 返回 `HTTP/1.1 200 OK`

### 10.2.5 本轮修正的启动链问题

- `docker-compose.yml` 默认初始化路径已由 `flask db-setup` 收敛为 `flask db upgrade`
- 已移除 `Dockerfile-API` 中依赖 GitHub 远程下载 `/wait` 的构建步骤，避免 TLS 超时导致构建失败
- 已调整 `Dockerfile-API` 分层顺序，固定系统依赖 / Python 依赖缓存，降低后续代码变更时的重建成本
- 已修正 `User.query.get('worker')` 在 PostgreSQL 下触发的整型 / 字符串不匹配问题
- 已修正 `common_employee.block` 写入布尔值导致 `cmdb-trigger` 启动失败的问题

---

## 十一、Phase 5：测试与回归

## 11.1 验收原则

本次改造不是“只要建表成功就算完成”。  
必须满足以下至少一组可交付标准：

### A 级标准（推荐）
- 空库初始化成功
- 核心单元测试通过
- 核心 API 冒烟测试通过
- Docker 启动闭环通过

### B 级标准（最低可接受）
- 空库初始化成功
- 核心接口人工验证通过
- 已记录残余风险和待补测试项

---

## 11.2 建议测试清单

### 11.2.1 后端单元测试
执行：

```bash
cd cmdb-api
pytest tests/ -v --tb=short
```

### 11.2.2 核心 API 冒烟验证
重点验证以下能力：

- 登录
- 创建 CI 类型
- 查询 CI 类型
- 创建属性
- 创建 CI
- 查询 CI
- 创建关系
- 搜索
- ACL 权限访问

### 11.2.3 前端验证
前端不是本次迁移的主要风险点，因此只做 smoke test：

- 登录页面可用
- 核心列表页可打开
- 常见接口不报错
- 创建/查询关键对象可完成

---

## 十二、详细施工清单

## 12.1 施工前检查清单

- [ ] 已确认当前是空库新项目
- [ ] 已确认无需历史数据迁移
- [ ] 已准备 PostgreSQL 16 环境
- [ ] 已具备回退到 Git 提交点的能力
- [ ] 已明确本次验收标准

## 12.2 Phase 0 清单

- [x] PostgreSQL 容器可启动
- [x] 可使用 PostgreSQL 连接串建立连接
- [x] `flask db-setup` 可执行
- [x] `flask cmdb-init-cache` 可执行
- [x] `flask cmdb-init-acl` 可执行
- [x] API / Celery 启动入口可导入
- [x] 已确认现有 Alembic 历史迁移链不适用于 PostgreSQL 空库
- [x] 已输出 blocker 列表

## 12.3 Phase 1 清单

- [ ] `requirements.txt` 已替换数据库驱动
- [ ] `settings.example.py` 已切换 PostgreSQL 配置
- [ ] `.env` 已切换到 `PG_*`
- [ ] `docker-compose.yml` 已替换数据库服务
- [ ] 启动脚本/部署脚本已去除 MySQL 依赖
- [ ] 文档已同步修订

## 12.4 Phase 2 清单

- [ ] MySQL 方言 `DOUBLE` 已替换
- [ ] Enum 策略已定稿为 `native_enum=False`
- [ ] Boolean / JSON / DateTime / 默认值已检查
- [ ] 自增主键与索引已检查
- [ ] PostgreSQL baseline migration 已重建
- [ ] 自动生成脚本已人工审核
- [ ] 空库迁移重复验证通过

## 12.5 Phase 3 清单

- [x] 原始 SQL 已完成兼容性扫描
- [x] 反引号问题已修正
- [x] MySQL 函数问题已修正
- [x] LIKE/ILIKE 语义已确认
- [x] 分页、排序、布尔表达式已验证

## 12.6 Phase 4 清单

- [x] 初始化命令执行成功
- [x] API 服务启动成功
- [x] Celery Worker 启动成功
- [x] Docker 启动闭环成功

## 12.7 Phase 5 清单

- [ ] 单元测试完成
- [ ] 核心 API 冒烟通过
- [ ] 前端 smoke test 通过
- [ ] 残余风险已记录
- [ ] 可交付结果已确认

---

## 十三、风险清单与应对策略

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 现有 Alembic 历史迁移链不适用于 PostgreSQL 空库 | 高 | 高 | 不再复用现有历史迁移链，重建 PostgreSQL baseline migration |
| Enum 原生类型管理复杂，导致迁移不稳定 | 中 | 高 | 默认采用 `native_enum=False`，不以 `postgresql.ENUM` 作为默认方案 |
| Alembic 自动生成脚本不完整或混入 MySQL 方言 | 中 | 高 | 仅将自动生成作为草稿，人工审核并手工修订脚本 |
| 原始 SQL 存在 MySQL 特有函数 | 中 | 中 | 全量搜索并逐项替换为 PostgreSQL 兼容写法 |
| `common-check-new-columns` 仍含 MySQL 方言 | 中 | 中 | 单独适配 `api/lib/common_setting/utils.py`，移除 MySQL `ENUM` 和反引号/`MODIFY COLUMN` 写法 |
| 初始化命令中隐含 MySQL 依赖 | 中 | 中 | 验证所有 CLI 初始化命令与启动脚本 |
| 布尔/时间/JSON 语义差异 | 中 | 中 | 增加专项检查与接口回归 |
| 大小写敏感导致查询行为变化 | 中 | 中 | 验证搜索、唯一性、模糊查询与排序 |
| Docker 启动链路不稳定 | 低 | 中 | 增加 healthcheck、依赖等待与完整启动验证 |

---

## 十四、推荐交付物

本次施工完成后，建议交付以下内容：

1. 改造后的代码
2. PostgreSQL 版本配置文件
3. PostgreSQL baseline migration 脚本
4. 测试与验证结果
5. 更新后的部署文档
6. 本文档作为唯一施工依据

---

## 十五、执行建议

## 15.1 是否建议继续推进
**建议继续推进。**

原因：

- 当前是空库新项目，迁移成本明显低于存量系统
- Flask + SQLAlchemy 技术栈具备较好的数据库抽象能力
- 当前主要风险集中且可验证
- 没有数据迁移链路，整体复杂度受控

## 15.2 最终建议

不要继续沿用“先试跑现有 Alembic，再视情况修修补补”的路线。  
应以本方案作为新的唯一基线，并按以下顺序执行：

1. 固化 Phase 0 结论：`native_enum=False`、`DOUBLE -> Float(precision=53)`、不复用现有历史迁移链
2. 进入 Phase 1 完成配置、依赖、Docker 与文档切换
3. 进入 Phase 2 完成模型兼容修正并重建 PostgreSQL baseline migration
4. 再进入原始 SQL、初始化链路、启动链路与回归验证

---

## 十六、归档说明

原有以下 4 份文档已不建议继续作为施工依据单独使用：

- `MIGRATION_TASK_BREAKDOWN.md`
- `MYSQL_TO_POSTGRESQL_NEW_PROJECT_ASSESSMENT.md`
- `PROJECT_ARCHITECTURE.md`
- `MYSQL_TO_POSTGRESQL_MIGRATION_ASSESSMENT.md`

原因：

- 内容存在重复
- 对风险和工期判断不完全一致
- 局部技术判断存在过度推断
- 适合作为历史分析材料，不适合作为唯一执行依据

建议将其统一归档，仅保留本文档作为当前阶段的正式施工方案。

---

## 十七、一句话结论

**本项目的 PostgreSQL 改造可以继续执行；Phase 0 已确认“连接、建表、初始化、启动入口”可行，但现有 Alembic 历史迁移链不适用，后续必须按“配置切换 + 模型兼容修正 + PostgreSQL baseline migration 重建 + 回归验证”的路线推进。**
