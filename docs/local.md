## 本地搭建: 环境和依赖

- 存储: PostgreSQL 16, redis
- python 版本: 3.8 <= python <= 3.11

## Install

- 启动 PostgreSQL 16 服务, redis 服务,此处以 docker 为例

```bash
mkdir ~/cmdb_db # 用于持久化存储PostgreSQL数据
docker run -d -p 5432:5432 --name postgres-cmdb -e POSTGRES_PASSWORD=Root_321 -e POSTGRES_USER=cmdb -e POSTGRES_DB=cmdb -v ~/cmdb_db:/var/lib/postgresql/data postgres:16
docker run -d --name redis -p 6379:6379 redis
```

- PostgreSQL 16 容器启动时已自动创建用户和数据库，无需额外设置 sql_mode。

- 拉取代码

```bash
git clone https://github.com/veops/cmdb.git
cd cmdb
cp cmdb-api/settings.example.py cmdb-api/settings.py
```

**设置 cmdb-api/settings.py 里的 database**

- 安装库
  - 后端: `cd cmdb-api && pipenv run pipenv install && cd ..`
  - 前端: `cd cmdb-ui && yarn install && cd ..`
    - node推荐使用14.x版本,推荐使用nvm进行nodejs版本管理：`nvm install 14 && nvm use 14`
- 可以将 docs/cmdb.sql 导入到数据库里,登录用户和密码分别是:demo/123456
- 创建数据库表: 进入**cmdb-api**目录执行 `pipenv run flask db-setup && pipenv run flask common-check-new-columns && pipenv run flask cmdb-init-cache`
- 启动服务

  - 后端: 进入**cmdb-api**目录执行 `pipenv run flask run -h 0.0.0.0`
  - 前端: 进入**cmdb-ui**目录执行`yarn run serve`
  - worker: 
    - 进入**cmdb-api**目录执行 `pipenv run celery -A celery_worker.celery worker -E -Q one_cmdb_async --autoscale=5,2 --logfile=one_cmdb_async.log -D`
    - 进入**cmdb-api**目录执行 `pipenv run celery -A celery_worker.celery worker -E -Q acl_async --autoscale=2,1 --logfile=one_acl_async.log -D`

  - 浏览器打开: [http://127.0.0.1:8000](http://127.0.0.1:8000)
    - 如果是非本机访问, 要修改**cmdb-ui/.env**里**VUE_APP_API_BASE_URL**里的 IP 地址为后端服务的 ip 地址
