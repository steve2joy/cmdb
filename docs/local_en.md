### Install

- Storage: postgresql, redis
- python version: 3.8 <= python <= 3.11

- Start PostgreSQL and Redis

  ```bash
  mkdir ~/cmdb_pgdata
  docker run -d -p 5432:5432 --name postgres-cmdb \
    -e POSTGRES_USER=cmdb \
    -e POSTGRES_PASSWORD=123456 \
    -e POSTGRES_DB=cmdb \
    -v ~/cmdb_pgdata:/var/lib/postgresql/data \
    postgres:16.13
  docker run -d --name redis -p 6379:6379 redis
  ```

- Pull code

  ```bash
  git clone https://github.com/veops/cmdb.git
  cd cmdb
  cp cmdb-api/settings.example.py cmdb-api/settings.py
  ```

  **set PostgreSQL / Redis connection in `cmdb-api/.env` or `cmdb-api/settings.py`**

- Install library
  - backend: `cd cmdb-api && pipenv install --dev && cd ..`
  - frontend: `cd cmdb-ui && yarn install && cd ..`
- Initialize database and cache in **cmdb-api**:
  `pipenv run flask db upgrade && pipenv run flask cmdb-init-cache && pipenv run flask cmdb-init-acl && pipenv run flask ensure-bootstrap-admin && pipenv run flask init-import-user-from-acl && pipenv run flask init-department`
- The default PostgreSQL path no longer uses `docs/cmdb.sql` / `docs/cmdb_en.sql`, and it does not run `flask common-check-new-columns`
- The default local admin comes from `BOOTSTRAP_ADMIN_*`, with username `admin` and password `123456` by default

- Start service

  - backend: in **cmdb-api** directory: `pipenv run flask run -h 0.0.0.0`
  - frontend: in **cmdb-ui** directory: `yarn run serve`
  - worker: 
    - in **cmdb-api** directory: `pipenv run celery -A celery_worker.celery worker -E -Q one_cmdb_async --autoscale=5,2 --logfile=one_cmdb_async.log -D`
    - in **cmdb-api** directory: `pipenv run celery -A celery_worker.celery worker -E -Q acl_async --autoscale=2,1 --logfile=one_acl_async.log -D`

  - homepage: [http://127.0.0.1:8000](http://127.0.0.1:8000)
    - if not run localhost: please change ip address(**VUE_APP_API_BASE_URL**) in config file **cmdb-ui/.env** into your backend ip address
