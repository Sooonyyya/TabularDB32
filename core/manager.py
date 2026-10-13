"""Єдина бізнес-логіка обох GUI. Невдала операція не змінює базу."""
from copy import deepcopy
from .models import Database, Table, Column, Row
from .data_types import ValidationError


class Manager:
    def __init__(self, database=None):
        # До явного створення або завантаження бази активної БД немає.
        self.db = database

    def require_database(self):
        if self.db is None:
            raise ValidationError('Спочатку створіть або завантажте базу даних.')
        return self.db

    @staticmethod
    def name(value):
        if not isinstance(value, str) or not value.strip():
            raise ValidationError('Назва не може бути порожньою.')
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValidationError('Назва містить недопустимі символи.')
        return value.strip()

    @staticmethod
    def index(index, size):
        if type(index) is not int or not 0 <= index < size:
            raise ValidationError('Оберіть наявний рядок або колонку.')

    def create_database(self, name):
        self.db = Database(self.name(name))
        return self.db

    def get_table(self, name):
        db = self.require_database()
        for table in db.tables:
            if table.name == name:
                return table
        raise ValidationError('Таблицю не знайдено.')

    def create_table(self, name):
        db = self.require_database()
        name = self.name(name)
        if any(t.name.casefold() == name.casefold() for t in db.tables):
            raise ValidationError('Таблиця з такою назвою вже існує.')
        table = Table(name)
        db.tables.append(table)
        return table

    def delete_table(self, name):
        db = self.require_database()
        db.tables.remove(self.get_table(name))

    def checked_column(self, table, column, ignore=None):
        column = deepcopy(column)
        column.name = self.name(column.name)
        # Створення column_type одночасно перевіряє тип і параметри меж.
        column.column_type
        if any(i != ignore and c.name.casefold() == column.name.casefold()
               for i, c in enumerate(table.columns)):
            raise ValidationError('Назви колонок мають бути унікальними.')
        return column

    def create_column(self, name, column, initial_value=''):
        table = self.get_table(name)
        column = self.checked_column(table, column)
        value = column.column_type.normalize(initial_value) if table.rows else None
        table.columns.append(column)
        for row in table.rows:
            row.values.append(value)

    def edit_column(self, name, index, column):
        table = self.get_table(name)
        self.index(index, len(table.columns))
        column = self.checked_column(table, column, index)
        # Спочатку перевіряємо всі наявні значення новим типом.
        # Тільки після успіху змінюємо схему та рядки.
        values = [column.column_type.normalize(row.values[index]) for row in table.rows]
        table.columns[index] = column
        for row, value in zip(table.rows, values):
            row.values[index] = value

    def delete_column(self, name, index):
        table = self.get_table(name)
        self.index(index, len(table.columns))
        if len(table.columns) == 1 and table.rows:
            raise ValidationError('Спочатку видаліть рядки: останню колонку заповненої таблиці видалити не можна.')
        table.columns.pop(index)
        for row in table.rows:
            row.values.pop(index)

    def normalized_row(self, table, values):
        if not table.columns:
            raise ValidationError('Спочатку створіть колонки таблиці.')
        if not isinstance(values, list) or len(values) != len(table.columns):
            raise ValidationError('Кількість значень не відповідає кількості колонок.')
        result = []
        for col, value in zip(table.columns, values):
            try:
                result.append(col.column_type.normalize(value))
            except ValidationError as exc:
                raise ValidationError(f'{col.name}: {exc}') from exc
        return result

    def create_row(self, name, values):
        table = self.get_table(name)
        table.rows.append(Row(self.normalized_row(table, values)))

    def edit_row(self, name, index, values):
        table = self.get_table(name)
        self.index(index, len(table.rows))
        row = Row(self.normalized_row(table, values))
        table.rows[index] = row

    def edit_cell(self, name, row_index, column_index, value):
        table = self.get_table(name)
        self.index(row_index, len(table.rows))
        self.index(column_index, len(table.columns))
        values = table.rows[row_index].values.copy()
        values[column_index] = value
        self.edit_row(name, row_index, values)

    def delete_row(self, name, index):
        table = self.get_table(name)
        self.index(index, len(table.rows))
        table.rows.pop(index)

    @staticmethod
    def are_tables_compatible(first, second):
        return first.columns == second.columns

    def union_tables(self, first_name, second_name, result_name):
        first, second = self.get_table(first_name), self.get_table(second_name)
        result_name = self.name(result_name)
        if not self.are_tables_compatible(first, second):
            raise ValidationError('Несумісні схеми: назви, порядок, типи та межі колонок мають збігатися.')
        db = self.require_database()
        if any(t.name.casefold() == result_name.casefold() for t in db.tables):
            raise ValidationError('Назва результату вже використовується.')
        result = Table(result_name, deepcopy(first.columns))
        seen = set()
        for source in (first, second):
            for row in source.rows:
                normalized = self.normalized_row(source, row.values)
                key = tuple(normalized)
                if key not in seen:
                    seen.add(key)
                    result.rows.append(Row(normalized))
        db.tables.append(result)
        return result

    def load_database(self, path):
        from .storage import load_database
        candidate = load_database(path)
        self.db = candidate
        return candidate

    def save_database(self, path):
        from .storage import save_database
        save_database(self.require_database(), path)
