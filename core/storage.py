"""JSON UTF-8, повна валідація і атомарна заміна файла."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from .manager import Manager
from .models import Column
from .data_types import ValidationError

FORMAT_VERSION = 1


def dumps(database):
    return json.dumps({'version': FORMAT_VERSION, 'database': asdict(database)},
                      ensure_ascii=False, indent=2, allow_nan=False)


def exact_keys(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValidationError('Некоректні поля структури JSON.')


def array(value):
    if not isinstance(value, list):
        raise ValidationError('Очікувався масив JSON.')
    return value


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError('Повторюване поле об’єкта JSON.')
        result[key] = value
    return result


def loads(text):
    try:
        data = json.loads(text, object_pairs_hook=unique_pairs)
        exact_keys(data, ('version', 'database'))
        if type(data['version']) is not int or data['version'] != FORMAT_VERSION:
            raise ValidationError('Непідтримувана версія формату.')
        db = data['database']
        exact_keys(db, ('name', 'tables'))
        manager = Manager()
        manager.create_database(db['name'])
        for item in array(db['tables']):
            exact_keys(item, ('name', 'columns', 'rows'))
            table = manager.create_table(item['name'])
            for col in array(item['columns']):
                exact_keys(col, ('name', 'kind', 'lower', 'upper'))
                manager.create_column(table.name, Column(**col))
            for row in array(item['rows']):
                exact_keys(row, ('values',))
                manager.create_row(table.name, row['values'])
        return manager.db
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f'Некоректний файл бази: {exc}') from exc


def load_database(path):
    try:
        return loads(Path(path).read_text(encoding='utf-8'))
    except UnicodeError as exc:
        raise ValidationError('Файл має бути текстом UTF-8.') from exc


def save_database(database, path):
    text = dumps(loads(dumps(database)))
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix='.db-', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
