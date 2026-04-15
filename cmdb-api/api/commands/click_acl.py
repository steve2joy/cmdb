import click
from flask import current_app
from flask.cli import with_appcontext

from api.lib.exception import AbortException
from api.lib.perm.acl.user import UserCRUD


@click.command()
@with_appcontext
def init_acl():
    """
    acl init
    """
    from api.models.acl import Role
    from api.models.acl import App
    from api.tasks.acl import role_rebuild
    from api.lib.perm.acl.const import ACL_QUEUE

    roles = Role.get_by(to_dict=False)
    apps = App.get_by(to_dict=False)
    for role in roles:
        if role.app_id:
            role_rebuild.apply_async(args=(role.id, role.app_id), queue=ACL_QUEUE)
        else:
            for app in apps:
                role_rebuild.apply_async(args=(role.id, app.id), queue=ACL_QUEUE)


@click.command()
@with_appcontext
def add_user():
    """
    create a user

    is_admin: default is False

    """

    from api.models.acl import App
    from api.lib.perm.acl.cache import AppCache
    from api.lib.perm.acl.cache import RoleCache
    from api.lib.perm.acl.role import RoleCRUD
    from api.lib.perm.acl.role import RoleRelationCRUD

    username = click.prompt('Enter username', confirmation_prompt=False)
    password = click.prompt('Enter password', hide_input=True, confirmation_prompt=True)
    email = click.prompt('Enter email   ', confirmation_prompt=False)
    is_admin = click.prompt('Admin (Y/N)   ', confirmation_prompt=False, type=bool, default=False)

    current_app.test_request_context().push()

    try:

        UserCRUD.add(username=username, password=password, email=email)

        if is_admin:
            app = AppCache.get('acl') or App.create(name='acl')
            acl_admin = RoleCache.get_by_name(None, 'acl_admin') or RoleCRUD.add_role('acl_admin', app.id, True)
            rid = RoleCache.get_by_name(None, username).id

            RoleRelationCRUD.add(acl_admin, acl_admin.id, [rid], app.id)

    except AbortException as e:
        print(f"Failed: {e}")


def _restore_or_init_user(username, password, email):
    from api.lib.perm.acl.cache import UserCache
    from api.models.acl import User

    user = User.get_by(username=username, first=True, to_dict=False, deleted=None)
    if user is None:
        return UserCRUD.add(username=username, password=password, email=email)

    updates = {}
    if user.deleted:
        updates["deleted"] = False
        updates["deleted_at"] = None
    if user.block:
        updates["block"] = False
    if not user.email:
        updates["email"] = email

    reset_password = current_app.config.get("BOOTSTRAP_ADMIN_RESET_PASSWORD", False)
    if reset_password or user.password is None:
        updates["password"] = password

    if updates:
        UserCache.clean(user)
        user = user.update(filter_none=False, **updates)

    return user


def _restore_or_init_role(name, app_id=None, is_app_admin=False, uid=None):
    from api.lib.perm.acl.cache import RoleCache
    from api.lib.perm.acl.role import RoleCRUD
    from api.models.acl import Role

    role = Role.get_by(name=name, app_id=app_id, first=True, to_dict=False, deleted=None)
    if role is None:
        return RoleCRUD.add_role(name, app_id, is_app_admin=is_app_admin, uid=uid)

    updates = {}
    if role.deleted:
        updates["deleted"] = False
        updates["deleted_at"] = None
    if uid is not None and role.uid != uid:
        updates["uid"] = uid
    if is_app_admin and not role.is_app_admin:
        updates["is_app_admin"] = True

    if updates:
        RoleCache.clean(role.id)
        RoleCache.clean_by_name(app_id, name)
        role = role.update(filter_none=False, **updates)

    return role


def _ensure_admin_employee(user, rid):
    from api.lib.common_setting.employee import EmployeeCRUD
    from api.models.common_setting import Employee

    employee = Employee.get_by(first=True, username=user.username, to_dict=False, deleted=None)
    if employee is None:
        EmployeeCRUD.add_employee_from_acl_created(
            uid=user.uid,
            rid=rid,
            username=user.username,
            nickname=user.nickname or user.username,
            email=user.email,
            block=user.block,
            avatar=user.avatar or "",
        )
        return

    updates = {}
    if employee.deleted:
        updates["deleted"] = False
        updates["deleted_at"] = None
    if employee.acl_uid != user.uid:
        updates["acl_uid"] = user.uid
    if employee.acl_rid != rid:
        updates["acl_rid"] = rid
    if employee.block != int(bool(user.block)):
        updates["block"] = int(bool(user.block))

    if updates:
        employee.update(filter_none=False, **updates)


@click.command("ensure-bootstrap-admin")
@with_appcontext
def ensure_bootstrap_admin():
    """
    Ensure the bootstrap admin account exists and has global admin privileges.
    """
    from api.lib.perm.acl.cache import AppCache
    from api.lib.perm.acl.cache import RoleRelationCache
    from api.lib.perm.acl.role import RoleRelationCRUD
    from api.models.acl import App

    if not current_app.config.get("BOOTSTRAP_ADMIN_ENABLED", True):
        click.echo("Skip bootstrap admin initialization: BOOTSTRAP_ADMIN_ENABLED is false")
        return

    username = current_app.config.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = current_app.config.get("BOOTSTRAP_ADMIN_PASSWORD", "123456")
    email = current_app.config.get("BOOTSTRAP_ADMIN_EMAIL", "admin@one-ops.com")

    if not username or not password or not email:
        raise click.ClickException("BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD / BOOTSTRAP_ADMIN_EMAIL must not be empty")

    current_app.test_request_context().push()

    acl_app = AppCache.get("acl") or App.create(name="acl")
    cmdb_app = AppCache.get("cmdb") or App.create(name="cmdb")
    user = _restore_or_init_user(username, password, email)
    user_role = _restore_or_init_role(username, uid=user.uid)
    acl_admin_role = _restore_or_init_role("acl_admin", is_app_admin=True)
    cmdb_admin_role = _restore_or_init_role("cmdb_admin", app_id=cmdb_app.id, is_app_admin=True)

    RoleRelationCRUD.add(acl_admin_role, acl_admin_role.id, [user_role.id], acl_app.id)
    RoleRelationCRUD.add(cmdb_admin_role, cmdb_admin_role.id, [user_role.id], cmdb_app.id)
    RoleRelationCache.clean(acl_admin_role.id, acl_app.id)
    RoleRelationCache.clean(cmdb_admin_role.id, cmdb_app.id)
    RoleRelationCache.clean(user_role.id, acl_app.id)
    RoleRelationCache.clean(user_role.id, cmdb_app.id)

    _ensure_admin_employee(user, user_role.id)

    click.echo(f"Bootstrap admin ensured: username={user.username}, email={user.email}")
