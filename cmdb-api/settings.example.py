# -*- coding: utf-8 -*-
"""Application configuration.

Most configuration is set via environment variables.

For local development, use a .env file to set
environment variables.
"""
from environs import Env

env = Env()
env.read_env()

ENV = env.str('FLASK_ENV', default='production')
DEBUG = ENV == 'development'
SECRET_KEY = env.str('SECRET_KEY')
BCRYPT_LOG_ROUNDS = env.int('BCRYPT_LOG_ROUNDS', default=13)
DEBUG_TB_ENABLED = DEBUG
DEBUG_TB_INTERCEPT_REDIRECTS = False

ERROR_CODES = [400, 401, 403, 404, 405, 500, 502]

PG_USER = env.str('PG_USER', default='cmdb')
PG_PASSWORD = env.str('PG_PASSWORD', default='123456')
PG_HOST = env.str('PG_HOST', default='127.0.0.1')
PG_PORT = env.int('PG_PORT', default=5432)
PG_DATABASE = env.str('PG_DATABASE', default='cmdb')
# # database
SQLALCHEMY_DATABASE_URI = (
    f'postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}'
)
SQLALCHEMY_BINDS = {
    'user': SQLALCHEMY_DATABASE_URI
}
SQLALCHEMY_ECHO = False
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

# # cache
CACHE_TYPE = 'redis'
CACHE_REDIS_HOST = env.str('CACHE_REDIS_HOST', default='127.0.0.1')
CACHE_REDIS_PORT = env.int('CACHE_REDIS_PORT', default=6379)
CACHE_REDIS_PASSWORD = env.str('CACHE_REDIS_PASSWORD', default='')
CACHE_KEY_PREFIX = 'CMDB::'
CACHE_DEFAULT_TIMEOUT = 3000

# # log
LOG_PATH = './logs/app.log'
LOG_LEVEL = 'DEBUG'

# # mail
MAIL_SERVER = ''
MAIL_PORT = 25
MAIL_USE_TLS = False
MAIL_USE_SSL = False
MAIL_DEBUG = True
MAIL_USERNAME = ''
MAIL_PASSWORD = ''
DEFAULT_MAIL_SENDER = ''

CELERY_BROKER_URL = env.str('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/2')
CELERY_RESULT_BACKEND = env.str('CELERY_RESULT_BACKEND', default=CELERY_BROKER_URL)

# # queue
CELERY = {
    'broker_url': CELERY_BROKER_URL,
    'result_backend': CELERY_RESULT_BACKEND,
    'broker_vhost': '/',
    'broker_connection_retry_on_startup': True
}
ONCE = {
    'backend': 'celery_once.backends.Redis',
    'settings': {
        'url': CELERY['broker_url'],
    }
}

# =============================== Authentication ===========================================================

# # CAS
CAS = dict(
    enabled=False,
    cas_server='https://{your-CASServer-hostname}',
    cas_validate_server='https://{your-CASServer-hostname}',
    cas_login_route='/cas/built-in/cas/login',
    cas_logout_route='/cas/built-in/cas/logout',
    cas_validate_route='/cas/built-in/cas/serviceValidate',
    cas_after_login='/',
    cas_user_map={
        'username': {'tag': 'cas:user'},
        'nickname': {'tag': 'cas:attribute', 'attrs': {'name': 'displayName'}},
        'email': {'tag': 'cas:attribute', 'attrs': {'name': 'email'}},
        'mobile': {'tag': 'cas:attribute', 'attrs': {'name': 'phone'}},
        'avatar': {'tag': 'cas:attribute', 'attrs': {'name': 'avatar'}},
    }
)

# # OAuth2.0
OAUTH2 = dict(
    enabled=False,
    client_id='',
    client_secret='',
    authorize_url='https://{your-OAuth2Server-hostname}/login/oauth/authorize',
    token_url='https://{your-OAuth2Server-hostname}/api/login/oauth/access_token',
    scopes=['profile', 'email'],
    user_info={
        'url': 'https://{your-OAuth2Server-hostname}/api/userinfo',
        'email': 'email',
        'username': 'name',
        'avatar': 'picture'
    },
    after_login='/'
)

# # OIDC
OIDC = dict(
    enabled=False,
    client_id='',
    client_secret='',
    authorize_url='https://{your-OIDCServer-hostname}/login/oauth/authorize',
    token_url='https://{your-OIDCServer-hostname}/api/login/oauth/access_token',
    scopes=['openid', 'profile', 'email'],
    user_info={
        'url': 'https://{your-OIDCServer-hostname}/api/userinfo',
        'email': 'email',
        'username': 'name',
        'avatar': 'picture'
    },
    after_login='/'
)

# # LDAP
LDAP = dict(
    enabled=False,
    ldap_server='',
    ldap_domain='',
    ldap_user_dn='cn={},ou=users,dc=xxx,dc=com'
)
# ==========================================================================================================

# # pagination
DEFAULT_PAGE_COUNT = 50

# # permission
WHITE_LIST = ['127.0.0.1']
USE_ACL = True

BOOTSTRAP_ADMIN_ENABLED = env.bool('BOOTSTRAP_ADMIN_ENABLED', default=True)
BOOTSTRAP_ADMIN_USERNAME = env.str('BOOTSTRAP_ADMIN_USERNAME', default='admin')
BOOTSTRAP_ADMIN_PASSWORD = env.str('BOOTSTRAP_ADMIN_PASSWORD', default='123456')
BOOTSTRAP_ADMIN_EMAIL = env.str('BOOTSTRAP_ADMIN_EMAIL', default='admin@one-ops.com')
BOOTSTRAP_ADMIN_RESET_PASSWORD = env.bool('BOOTSTRAP_ADMIN_RESET_PASSWORD', default=False)

# # elastic search
ES_HOST = '127.0.0.1'
USE_ES = False

BOOL_TRUE = ['true', 'TRUE', 'True', True, '1', 1, 'Yes', 'YES', 'yes', 'Y', 'y']

# # messenger
USE_MESSENGER = True

# # secrets
SECRETS_ENGINE = 'inner'  # 'inner' or 'vault'
VAULT_URL = ''
VAULT_TOKEN = ''
INNER_TRIGGER_TOKEN = ''
