# -*- coding:utf-8 -*-

import datetime
import re

import six

from api.extensions import db
from api.lib.exception import CommitException


_INT_PATTERN = re.compile(r"^-?\d+$")
_FLOAT_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")
_BOOL_TRUE_VALUES = {True, 1, "1", "true", "True", "TRUE", "t", "T", "yes", "Yes", "YES", "y", "Y", "on", "ON"}
_BOOL_FALSE_VALUES = {
    False, 0, "0", "false", "False", "FALSE", "f", "F", "no", "No", "NO", "n", "N", "off", "OFF"
}


class FormatMixin(object):
    def to_dict(self):
        res = dict()
        for k in getattr(self, "__mapper__").c.keys():
            if k in {'password', '_password', 'secret', '_secret'}:
                continue

            if k.startswith('_'):
                k = k[1:]

            if not isinstance(getattr(self, k), (datetime.datetime, datetime.date, datetime.time)):
                res[k] = getattr(self, k)
            else:
                res[k] = str(getattr(self, k))

        return res
    
    @classmethod
    def from_dict(cls, **kwargs):
        from sqlalchemy.sql.sqltypes import Time, Date, DateTime

        columns = dict(getattr(cls, "__table__").columns)

        for k, c in columns.items():
            if kwargs.get(k):
                if type(c.type) == Time:
                    kwargs[k] = datetime.datetime.strptime(kwargs[k], "%H:%M:%S").time()
                if type(c.type) == Date:
                    kwargs[k] = datetime.datetime.strptime(kwargs[k], "%Y-%m-%d").date()
                if type(c.type) == DateTime:
                    kwargs[k] = datetime.datetime.strptime(kwargs[k], "%Y-%m-%d %H:%M:%S")

        return cls(**kwargs)

    @classmethod
    def get_columns(cls):
        return {k: 1 for k in getattr(cls, "__mapper__").c.keys()}


class CRUDMixin(FormatMixin):
    @classmethod
    def create(cls, flush=False, commit=True, **kwargs):
        return cls(**kwargs).save(flush=flush, commit=commit)

    def update(self, flush=False, commit=True, filter_none=True, **kwargs):
        kwargs.pop("id", None)
        for attr, value in six.iteritems(kwargs):
            if (value is not None and filter_none) or not filter_none:
                setattr(self, attr, value)

        return self.save(flush=flush, commit=commit)

    def save(self, commit=True, flush=False):
        db.session.add(self)
        try:
            if flush:
                db.session.flush()
            elif commit:
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise CommitException(str(e))

        return self

    def delete(self, flush=False, commit=True):
        db.session.delete(self)
        try:
            if flush:
                return db.session.flush()
            elif commit:
                return db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise CommitException(str(e))

    def soft_delete(self, flush=False, commit=True):
        setattr(self, "deleted", True)
        setattr(self, "deleted_at", datetime.datetime.now())
        self.save(flush=flush, commit=commit)

    @classmethod
    def get_by_id(cls, _id):
        if any((isinstance(_id, six.string_types) and _id.isdigit(),
                isinstance(_id, (six.integer_types, float))), ):
            obj = getattr(cls, "query").get(int(_id))
            if obj and not getattr(obj, 'deleted', False):
                return obj

    @classmethod
    def get_by(cls, first=False,
               to_dict=True,
               fl=None,
               exclude=None,
               deleted=False,
               use_master=False,
               only_query=False,
               **kwargs):
        db_session = db.session if not use_master else db.session().using_bind("master")
        fl = fl.strip().split(",") if fl and isinstance(fl, six.string_types) else (fl or [])
        exclude = exclude.strip().split(",") if exclude and isinstance(exclude, six.string_types) else (exclude or [])

        keys = cls.get_columns()
        fl = [k for k in fl if k in keys]
        fl = [k for k in keys if k not in exclude and not k.isupper()] if exclude else fl
        fl = list(filter(lambda x: "." not in x, fl))

        if hasattr(cls, "deleted") and deleted is not None:
            kwargs["deleted"] = deleted

        kwargs_for_func = {i[7:]: kwargs[i] for i in kwargs if i.startswith('__func_')}
        kwargs = {i: kwargs[i] for i in kwargs if not i.startswith('__func_')}
        kwargs = {i: normalize_model_filter_value(cls, i, kwargs[i]) for i in kwargs}

        if fl:
            query = db_session.query(*[getattr(cls, k) for k in fl])
        else:
            query = db_session.query(cls)

        query = query.filter_by(**kwargs)
        for i in kwargs_for_func:
            func, key = i.split('__key_')
            value = normalize_model_filter_value(cls, key, kwargs_for_func[i], func_name=func)
            query = query.filter(getattr(getattr(cls, key), func)(value))

        if only_query:
            return query

        if fl:
            result = [{k: getattr(i, k) for k in fl} if to_dict else i for i in query]
        else:
            result = [i.to_dict() if to_dict else i for i in query]

        return result[0] if first and result else (None if first else result)

    @classmethod
    def get_by_like(cls, to_dict=True, deleted=False, **kwargs):
        query = db.session.query(cls)
        if hasattr(cls, "deleted") and deleted is not None:
            query = query.filter(cls.deleted.is_(deleted))

        for k, v in kwargs.items():
            query = query.filter(getattr(cls, k).ilike('%{0}%'.format(v)))
        return [i.to_dict() if to_dict else i for i in query]


class SoftDeleteMixin(object):
    deleted_at = db.Column(db.DateTime)
    deleted = db.Column(db.Boolean, index=True, default=False)


class TimestampMixin(object):
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now())
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.datetime.now())


class TimestampMixin2(object):
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(), index=True)


class SurrogatePK(object):
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)


class Model(SoftDeleteMixin, TimestampMixin, CRUDMixin, db.Model, SurrogatePK):
    __abstract__ = True


class CRUDModel(db.Model, CRUDMixin):
    __abstract__ = True


class Model2(TimestampMixin2, db.Model, CRUDMixin, SurrogatePK):
    __abstract__ = True


def get_model_column(cls, key):
    attr = getattr(cls, key, None)
    prop = getattr(attr, "property", None)
    columns = getattr(prop, "columns", None)
    if columns:
        return columns[0]


def get_model_column_python_type(cls, key):
    column = get_model_column(cls, key)
    if column is None:
        return None

    try:
        return column.type.python_type
    except (AttributeError, NotImplementedError):
        return None


def normalize_model_filter_value(cls, key, value, func_name=None, strict=False):
    column = get_model_column(cls, key)
    if column is None:
        return value

    if func_name in {"in_", "notin_"}:
        if isinstance(value, six.string_types):
            values = [i.strip() for i in value.split(",") if i.strip() != ""]
        elif isinstance(value, (list, tuple, set)):
            values = list(value)
        else:
            values = [value]

        return [_normalize_scalar_filter_value(column, item, strict=strict) for item in values]

    return _normalize_scalar_filter_value(column, value, strict=strict)


def normalize_model_filter_kwargs(cls, kwargs, keys=None, strict=False):
    normalized = dict(kwargs)

    for key in keys or list(normalized.keys()):
        if key not in normalized:
            continue

        column = get_model_column(cls, key)
        if column is None:
            continue

        try:
            normalized[key] = normalize_model_filter_value(cls, key, normalized[key], strict=strict)
        except ValueError:
            raise ValueError(key)

    return normalized


def _normalize_scalar_filter_value(column, value, strict=False):
    if value is None:
        return value

    if isinstance(value, six.string_types):
        value = value.strip()
        if value == "":
            return value

    try:
        python_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        return value

    if python_type is bool:
        if value in _BOOL_TRUE_VALUES:
            return True
        if value in _BOOL_FALSE_VALUES:
            return False
        if strict:
            raise ValueError(value)
        return value

    if python_type is int and not isinstance(value, bool):
        if isinstance(value, six.integer_types):
            return int(value)
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, six.string_types) and _INT_PATTERN.match(value):
            return int(value)
        if strict:
            raise ValueError(value)
        return value

    if python_type is float and not isinstance(value, bool):
        if isinstance(value, (six.integer_types, float)):
            return float(value)
        if isinstance(value, six.string_types) and _FLOAT_PATTERN.match(value):
            return float(value)
        if strict:
            raise ValueError(value)

    return value


def CompatEnum(*values, **kwargs):
    # Use non-native enums so PostgreSQL precheck does not rely on named enum types.
    kwargs.setdefault("native_enum", False)
    return db.Enum(*values, **kwargs)


def get_dialect_name(bind=None):
    bind = bind or db.session.get_bind()
    return bind.dialect.name if bind is not None else ""


def get_regex_operator(bind=None):
    return "~" if get_dialect_name(bind) == "postgresql" else "regexp"
