## 使用Flask-Migrate做数据库版本管理

### 当前 PostgreSQL 迁移状态

- 现有 `cmdb-api/migrations/versions` 历史链路默认面向 MySQL，不能直接用于 PostgreSQL 空库初始化
- PostgreSQL 默认初始化路径请使用 `flask db-setup`，不要直接对空库执行现有 `flask db upgrade`
- PostgreSQL baseline migration 需要单独重建，自动生成结果也需要人工审核后再提交

### 进入 cmdb-api 后再执行下面步骤

- 对已经完成基线初始化、且迁移链已切到 PostgreSQL 的数据库，执行 `flask db migrate`
- 审核生成的迁移文件后，再执行 `flask db upgrade`


### tips

- cmdb-api/migrations/env.py文件内的exclude_tables列表可以填写不想被flask-migrate管理的数据库表
