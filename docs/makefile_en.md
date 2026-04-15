### Install by Makefile

- Start PostgreSQL and Redis
- Pull code

  ```bash
  git clone https://github.com/veops/cmdb.git
  cd cmdb
  cp cmdb-api/settings.example.py cmdb-api/settings.py
  ```

  **set PostgreSQL / Redis connection in `cmdb-api/.env` or `cmdb-api/settings.py`**

- In cmdb directory,start in order as follows:
  - environment: `make env`
  - local temporary services: `make docker-postgres` and `make docker-redis`
  - start API: `make api`
  - start UI: `make ui`
  - start worker: `make worker`
