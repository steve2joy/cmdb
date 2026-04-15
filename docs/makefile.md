## Install by Makefile

- 启动 postgresql 服务, redis 服务

- 拉取代码

```bash
git clone https://github.com/veops/cmdb.git
cd cmdb
cp cmdb-api/settings.example.py cmdb-api/settings.py
```

**设置 `cmdb-api/.env` 或 `cmdb-api/settings.py` 里的 PostgreSQL / Redis 连接信息**

- 顺序在 cmdb 目录下执行
  - 环境: `make env`
  - 如需本地临时数据库: `make docker-postgres` 和 `make docker-redis`
  - 启动 API: `make api`
  - 启动 UI: `make ui`
  - 启动 worker: `make worker`
