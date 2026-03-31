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

## 六、Phase 0：技术预验证（强制增加）

> 目标：在正式施工前，快速确认最关键的技术假设是否成立。  
> 这是本方案相对于原 4 份文档最重要的修订点。

## 6.1 目标

确认以下问题：

1. 仅替换驱动与连接串后，应用能否连接 PostgreSQL
2. 当前 `db.Enum(...)` 是否真的需要全面改造
3. `flask db migrate / upgrade` 是否能在 PostgreSQL 下跑通
4. 是否存在明显的原始 SQL 不兼容问题
5. 初始化命令是否能成功执行
6. API/Celery 的启动链路是否依赖 MySQL 特定逻辑

## 6.2 预验证输出

Phase 0 结束后，必须产出以下结论：

- Enum 最终采用哪种策略
- Alembic 迁移脚本能否自动生成
- 哪些文件必须修改
- 哪些问题只是文档层面的风险，不构成阻塞
- 是否进入正式施工

## 6.3 执行步骤

### 步骤 0.1：准备 PostgreSQL 16 环境
建议优先使用 Docker，避免本机环境污染。

示例：

```yaml
cmdb-db:
  image: postgres:16-alpine
  container_name: cmdb-db
  environment:
    POSTGRES_USER: cmdb
    POSTGRES_PASSWORD: 123456
    POSTGRES_DB: cmdb
    TZ: Asia/Shanghai
  ports:
    - "5432:5432"
  volumes:
    - db-data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U cmdb"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### 步骤 0.2：仅替换连接驱动与数据库 URI
先不做大面积模型改造，观察应用是否能建立连接。

### 步骤 0.3：尝试执行迁移命令

```bash
cd cmdb-api
flask db migrate -m "postgres precheck"
flask db upgrade
```

### 步骤 0.4：执行基础初始化命令

```bash
flask cmdb-init-cache
flask cmdb-init-acl
```

### 步骤 0.5：记录 blocker
对失败点分类：

- 连接层问题
- Enum 问题
- Alembic 迁移问题
- SQL 兼容问题
- 初始化脚本问题
- 启动链路问题

---

## 七、Phase 1：依赖、配置与 Docker 改造

## 7.1 改造目标

完成 PostgreSQL 基础接入，使项目的运行配置不再依赖 MySQL。

## 7.2 涉及文件

- `cmdb-api/requirements.txt`
- `cmdb-api/settings.example.py`
- `cmdb-api/.env`
- 根目录 `.env`
- `docker-compose.yml`
- `Makefile` / `install.sh` / 文档中所有可能引用 MySQL 的地方

## 7.3 具体任务

### 任务 1.1：替换数据库驱动

建议修改：

```diff
- PyMySQL==1.1.0
+ psycopg2-binary==2.9.9
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

## 八、Phase 2：模型层与迁移层改造

## 8.1 改造原则

这一阶段不建议盲目“全面 PostgreSQL 方言化”。  
建议遵循以下优先级：

1. **能用标准 SQLAlchemy 类型解决的，优先用标准类型**
2. **先验证现有 `db.Enum(...)` 是否可用**
3. **只有在验证失败时，才引入 PostgreSQL 原生 ENUM 或其他替代方案**
4. **Alembic 生成脚本必须人工审查**

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

## 8.3 Enum 改造策略（本方案重点修订）

## 8.3.1 原则

原文档将所有枚举字段直接改造成 `postgresql.ENUM`，这个策略**不建议直接采用**。  
更稳妥的顺序如下：

### 方案优先级

#### 方案 A：优先验证现有 `db.Enum(...)` 是否直接可用
如果：

- `flask db migrate` 能生成脚本
- `flask db upgrade` 能正常建表
- CRUD 与默认值正常

则优先保留现有 `db.Enum(...)` 方案。

#### 方案 B：保留 `db.Enum(...)`，但显式控制参数
可视验证结果考虑：

- `native_enum=True/False`
- 显式设置 `name=...`
- 解决同名枚举冲突

#### 方案 C：改为 `String + CheckConstraint` 或应用层校验
如果 PostgreSQL 原生 enum 带来过多维护成本，可退化为：

- `db.String(...)`
- Python 枚举校验
- 必要时增加 `CheckConstraint`

#### 方案 D：仅在必要时使用 `postgresql.ENUM`
只有当 A/B/C 均不满足需求，且确实需要数据库强约束时，才使用原生 PG ENUM。

---

## 8.3.2 为什么不建议一开始全量改成 PG ENUM

风险包括但不限于：

- 枚举类型全局命名冲突
- Alembic 自动生成不稳定
- 多个字段复用同名类型时维护复杂
- 后续新增枚举值的数据库演进成本高
- downgrade 更麻烦

因此，**先验证、后决定策略** 才是可施工方案。

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

## 8.5 Alembic 迁移脚本要求

## 8.5.1 不可直接信任自动生成结果
所有 `flask db migrate` 生成的迁移脚本，必须人工审核以下内容：

- enum 类型创建/删除
- 索引
- 唯一约束
- foreign key
- server default
- JSON 字段
- 布尔默认值
- 时间字段默认值

## 8.5.2 验证标准
迁移脚本至少要在**空库**上验证以下两次：

1. `upgrade` 成功
2. 删除数据库后重新建空库再次 `upgrade` 成功

---

## 九、Phase 3：原始 SQL 与查询兼容性改造

## 9.1 涉及位置

重点检查以下文件：

- `cmdb-api/api/lib/cmdb/query_sql.py`
- `cmdb-api/api/lib/cmdb/search/ci/db/query_sql.py`

如有需要，继续扩展搜索：

- `search/`
- `tasks/`
- `lib/`
- `views/`

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

## 十、Phase 4：初始化链路与运行链路验证

## 10.1 验证目标

保证项目不只是“能建表”，而是“能启动、能初始化、能跑核心流程”。

## 10.2 重点验证项

### 10.2.1 初始化命令
必须验证：

```bash
flask cmdb-init-cache
flask cmdb-init-acl
```

### 10.2.2 API 服务启动
验证：

- Flask / Gunicorn 正常启动
- 能连接 PostgreSQL
- 不再引用 MySQL 环境变量
- 不存在启动时数据库初始化脚本失败

### 10.2.3 Celery Worker 启动
验证：

- Worker 正常启动
- 不因数据库连接配置变化失败
- 与 Redis / PostgreSQL 都能正常工作

### 10.2.4 Docker 启动闭环
验证通过 `docker-compose up` 能完成：

- PostgreSQL ready
- Redis ready
- API ready
- UI ready
- Celery ready（如当前部署方式启用）

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

- [ ] PostgreSQL 容器可启动
- [ ] 可使用 PostgreSQL 连接串建立连接
- [ ] `flask db migrate` 可执行
- [ ] `flask db upgrade` 可执行
- [ ] `flask cmdb-init-cache` 可执行
- [ ] `flask cmdb-init-acl` 可执行
- [ ] 已输出 blocker 列表

## 12.3 Phase 1 清单

- [ ] `requirements.txt` 已替换数据库驱动
- [ ] `settings.example.py` 已切换 PostgreSQL 配置
- [ ] `.env` 已切换到 `PG_*`
- [ ] `docker-compose.yml` 已替换数据库服务
- [ ] 启动脚本/部署脚本已去除 MySQL 依赖
- [ ] 文档已同步修订

## 12.4 Phase 2 清单

- [ ] MySQL 方言 `DOUBLE` 已替换
- [ ] Enum 策略已根据验证结果定稿
- [ ] Boolean / JSON / DateTime / 默认值已检查
- [ ] 自增主键与索引已检查
- [ ] Alembic 脚本已人工审核
- [ ] 空库迁移重复验证通过

## 12.5 Phase 3 清单

- [ ] 原始 SQL 已完成兼容性扫描
- [ ] 反引号问题已修正
- [ ] MySQL 函数问题已修正
- [ ] LIKE/ILIKE 语义已确认
- [ ] 分页、排序、布尔表达式已验证

## 12.6 Phase 4 清单

- [ ] 初始化命令执行成功
- [ ] API 服务启动成功
- [ ] Celery Worker 启动成功
- [ ] Docker 启动闭环成功

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
| Enum 在 PostgreSQL 下迁移失败 | 中 | 高 | 先做 Phase 0 验证，必要时改为 `native_enum=False` 或 `String + CheckConstraint` |
| Alembic 自动生成脚本不完整 | 中 | 高 | 人工审核并手工修订迁移脚本 |
| 原始 SQL 存在 MySQL 特有函数 | 中 | 中 | 全量搜索并逐项替换为 PostgreSQL 兼容写法 |
| 初始化命令中隐含 MySQL 依赖 | 中 | 中 | 验证所有 CLI 初始化命令与启动脚本 |
| 布尔/时间/JSON 语义差异 | 中 | 中 | 增加专项检查与接口回归 |
| 大小写敏感导致查询行为变化 | 中 | 中 | 验证搜索、唯一性、模糊查询与排序 |
| Docker 启动链路不稳定 | 低 | 中 | 增加 healthcheck、依赖等待与完整启动验证 |

---

## 十四、推荐交付物

本次施工完成后，建议交付以下内容：

1. 改造后的代码
2. PostgreSQL 版本配置文件
3. 可执行的迁移脚本
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

不要直接把旧文档中的拆解当成最终施工计划。  
应以本方案作为新的唯一基线，并按以下顺序执行：

1. 先做 Phase 0 技术预验证
2. 根据验证结果确定 Enum 最终策略
3. 再进入正式代码改造
4. 以空库初始化与核心流程回归作为交付依据

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

**本项目的 PostgreSQL 改造可以执行；以“先做技术预验证、再完成配置/模型/SQL/迁移/初始化/回归”的方式推进，整体风险可控，建议按 4~7 人天组织实施。**