# -*- coding:utf-8 -*-
from datetime import datetime
from flask import current_app
from sqlalchemy import Index
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from api.extensions import db


def get_cur_time_str(split_flag='-'):
    f = f"%Y{split_flag}%m{split_flag}%d{split_flag}%H{split_flag}%M{split_flag}%S{split_flag}%f"
    return datetime.now().strftime(f)[:-3]


class BaseEnum(object):
    _ALL_ = None

    @classmethod
    def is_valid(cls, item):
        return item in cls.all()

    @classmethod
    def all(cls):
        if cls._ALL_ is None:
            values = []
            seen = set()
            for attr, value in cls.__dict__.items():
                if attr.startswith("_") or callable(value):
                    continue
                if value in seen:
                    continue
                values.append(value)
                seen.add(value)
            cls._ALL_ = tuple(values)
        return cls._ALL_


class CheckNewColumn(object):

    def __init__(self):
        self.engine = db.get_engine()
        self.inspector = inspect(self.engine)
        self.table_names = self.inspector.get_table_names()
        self.preparer = self.engine.dialect.identifier_preparer

    @staticmethod
    def is_enum_type(column_type):
        enums = getattr(column_type, 'enums', None)
        return bool(enums)

    def quote_identifier(self, name):
        return self.preparer.quote(name)

    @staticmethod
    def get_model_by_table_name(_table_name):
        registry = getattr(db.Model, 'registry', None)
        class_registry = getattr(registry, '_class_registry', None)
        for _model in class_registry.values():
            if hasattr(_model, '__tablename__') and _model.__tablename__ == _table_name:
                return _model
        return None

    def run(self):
        for table_name in self.table_names:
            self.check_by_table(table_name)

    def check_by_table(self, table_name):
        existed_columns = self.inspector.get_columns(table_name)
        enum_columns = []
        existed_column_name_list = []
        for c in existed_columns:
            if self.is_enum_type(c['type']):
                enum_columns.append(c['name'])
            existed_column_name_list.append(c['name'])

        model = self.get_model_by_table_name(table_name)
        if model is None:
            return
        model_columns = getattr(getattr(getattr(model, '__table__'), 'columns'), '_all_columns')
        for column in model_columns:
            if column.name not in existed_column_name_list:
                add_res = self.add_new_column(table_name, column)
                if not add_res:
                    continue

                current_app.logger.info(f"add new column [{column.name}] in table [{table_name}] success.")

                if column.name in enum_columns:
                    enum_columns.remove(column.name)

                self.add_new_index(table_name, column)

        if len(enum_columns) > 0:
            self.check_enum_column(enum_columns, existed_columns, model_columns, table_name)

    def add_new_column(self, target_table_name, new_column):
        try:
            sql = "ALTER TABLE {0} ADD COLUMN {1}".format(
                self.quote_identifier(target_table_name),
                CreateColumn(new_column).compile(dialect=self.engine.dialect),
            )
            with self.engine.begin() as conn:
                conn.execute(text(sql))
            return True
        except Exception as e:
            err = f"add_new_column [{new_column.name}] to table [{target_table_name}] err: {e}"
            current_app.logger.error(err)
            return False

    def add_new_index(self, target_table_name, new_column):
        try:
            if new_column.index:
                index_name = f"{target_table_name}_{new_column.name}"
                with self.engine.begin() as conn:
                    Index(index_name, new_column).create(bind=conn)
                current_app.logger.info(f"add new index [{index_name}] in table [{target_table_name}] success.")

            return True
        except Exception as e:
            err = f"add_new_index [{new_column.name}] to table [{target_table_name}] err: {e}"
            current_app.logger.error(err)
            return False

    def check_enum_column(self, enum_columns, existed_columns, model_columns, table_name):
        if self.engine.dialect.name != 'mysql':
            current_app.logger.info(
                f"skip enum column sync for table [{table_name}] on dialect [{self.engine.dialect.name}]")
            return

        for column_name in enum_columns:
            try:
                enum_column = list(filter(lambda x: x['name'] == column_name, existed_columns))[0]
                old_enum_value = enum_column.get('type', {}).enums
                target_column = list(filter(lambda x: x.name == column_name, model_columns))[0]
                new_enum_value = getattr(target_column.type, 'enums', None)

                if not new_enum_value or set(old_enum_value) == set(new_enum_value):
                    continue

                enum_values_str = ','.join(["'{}'".format(value) for value in new_enum_value])
                sql = (
                    f"ALTER TABLE {self.quote_identifier(table_name)} MODIFY COLUMN "
                    f"{self.quote_identifier(column_name)} enum({enum_values_str})"
                )
                with self.engine.begin() as conn:
                    conn.execute(text(sql))
                current_app.logger.info(
                    f"modify column [{column_name}] ENUM: {new_enum_value} in table [{table_name}] success.")
            except Exception as e:
                current_app.logger.error(
                    f"modify column  ENUM [{column_name}] in table [{table_name}] err: {e}")
