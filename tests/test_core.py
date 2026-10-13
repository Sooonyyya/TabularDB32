import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from core.data_types import (IntegerType, RealType, CharType, StringType,
                             CharInvlType, StringCharInvlType, ValidationError)
from core.models import Column
from core.manager import Manager
from core.storage import dumps, loads

class TypeTests(unittest.TestCase):
    def test_integer_normalization(self):
        self.assertEqual(IntegerType().normalize('+001'), '1')
        self.assertEqual(IntegerType().normalize('-000'), '0')
        self.assertFalse(IntegerType().validation('1.5'))

    def test_real_equivalent_notations(self):
        self.assertEqual(RealType().normalize('1e0'), RealType().normalize('1.00'))
        self.assertEqual(RealType().normalize('-0'), '0.0')

    def test_real_rejects_nonfinite(self):
        for value in ('NaN', 'inf', '1e999', '1,5'):
            self.assertFalse(RealType().validation(value))

    def test_char_unicode_and_length(self):
        self.assertTrue(CharType().validation('ї'))
        self.assertTrue(CharType().validation('😀'))
        for value in ('', 'аб', '\ud800'):
            self.assertFalse(CharType().validation(value))

    def test_string_preserves_spaces_and_empty(self):
        for value in ('', '  abc  ', 'рядок\nдва'):
            self.assertEqual(StringType().normalize(value), value)

    def test_interval_char_endpoints(self):
        kind = CharInvlType('a', 'm')
        self.assertTrue(kind.validation('a'))
        self.assertTrue(kind.validation('m'))
        self.assertTrue(kind.validation('f'))

    def test_interval_char_rejects_outside_wrong_length_and_reversed_bounds(self):
        kind = CharInvlType('a', 'm')
        for value in ('n', 'A', '', 'ab'):
            self.assertFalse(kind.validation(value))
        with self.assertRaises(ValidationError):
            CharInvlType('z', 'a')

    def test_bounded_string_endpoints_and_empty(self):
        kind = StringCharInvlType('a', 'z')
        for value in ('az', 'abc', ''):
            self.assertTrue(kind.validation(value))
        self.assertFalse(kind.validation('A'))
        self.assertFalse(kind.validation('a b'))

    def test_bounded_string_rejects_reversed_bounds(self):
        with self.assertRaises(ValidationError):
            StringCharInvlType('z', 'a')

class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.m = Manager()
        self.m.create_database('Test')
        for name in ('A', 'B'):
            self.m.create_table(name)
            self.m.create_column(name, Column('id', 'integer'))
            self.m.create_column(name, Column('text', 'string'))

    def test_union_removes_duplicates_and_normalizes(self):
        self.m.create_row('A', ['01', 'abc'])
        self.m.create_row('A', ['1', 'abc'])
        self.m.create_row('B', ['+1', 'abc'])
        self.m.create_row('B', ['2', 'def'])
        result = self.m.union_tables('A', 'B', 'U')
        self.assertEqual([r.values for r in result.rows], [['1', 'abc'], ['2', 'def']])

    def test_union_does_not_alias_sources(self):
        self.m.create_row('A', ['1', 'x'])
        self.m.union_tables('A', 'B', 'U')
        self.m.edit_cell('U', 0, 1, 'changed')
        self.m.edit_column('U', 1, Column('renamed', 'string'))
        self.assertEqual(self.m.get_table('A').rows[0].values, ['1', 'x'])
        self.assertEqual(self.m.get_table('A').columns[1].name, 'text')

    def test_union_empty_tables(self):
        self.assertEqual(self.m.union_tables('A', 'B', 'U').rows, [])

    def test_union_same_table(self):
        self.m.create_row('A', ['1', 'x'])
        self.m.create_row('A', ['1', 'x'])
        self.assertEqual(len(self.m.union_tables('A', 'A', 'U').rows), 1)

    def test_union_rejects_schema_mismatch_atomically(self):
        self.m.edit_column('B', 1, Column('other', 'string'))
        before = dumps(self.m.db)
        with self.assertRaises(ValidationError):
            self.m.union_tables('A', 'B', 'U')
        self.assertEqual(dumps(self.m.db), before)

    def test_union_rejects_different_bounds(self):
        self.m.edit_column('A', 1, Column('text', 'string(charInvl)', 'a', 'z'))
        self.m.edit_column('B', 1, Column('text', 'string(charInvl)', 'a', 'f'))
        with self.assertRaises(ValidationError):
            self.m.union_tables('A', 'B', 'U')

    def test_union_rejects_existing_name(self):
        with self.assertRaises(ValidationError):
            self.m.union_tables('A', 'B', 'a')

    def test_edit_invalid_row_is_atomic(self):
        self.m.create_row('A', ['1', 'abc'])
        before = dumps(self.m.db)
        with self.assertRaises(ValidationError):
            self.m.edit_row('A', 0, ['wrong', 'changed'])
        self.assertEqual(dumps(self.m.db), before)

    def test_create_row_width_validation(self):
        with self.assertRaises(ValidationError):
            self.m.create_row('A', ['1'])
        self.assertEqual(self.m.get_table('A').rows, [])

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValidationError):
            self.m.create_table(' a ')
        with self.assertRaises(ValidationError):
            self.m.create_column('A', Column('ID', 'string'))

    def test_add_column_with_default_to_existing_rows(self):
        self.m.create_row('A', ['1', 'abc'])
        self.m.create_column('A', Column('flag', 'char'), 'x')
        self.assertEqual(self.m.get_table('A').rows[0].values, ['1', 'abc', 'x'])

    def test_invalid_default_is_atomic(self):
        self.m.create_row('A', ['1', 'abc'])
        before = dumps(self.m.db)
        with self.assertRaises(ValidationError):
            self.m.create_column('A', Column('flag', 'char'), '')
        self.assertEqual(dumps(self.m.db), before)

    def test_change_column_validates_all_rows(self):
        self.m.create_row('A', ['1', '123'])
        self.m.create_row('A', ['2', 'abc'])
        before = dumps(self.m.db)
        with self.assertRaises(ValidationError):
            self.m.edit_column('A', 1, Column('text', 'integer'))
        self.assertEqual(dumps(self.m.db), before)

    def test_delete_column_keeps_alignment(self):
        self.m.create_row('A', ['1', 'abc'])
        self.m.delete_column('A', 0)
        self.assertEqual(self.m.get_table('A').rows[0].values, ['abc'])
        with self.assertRaises(ValidationError):
            self.m.delete_column('A', 0)

    def test_delete_row_and_table(self):
        self.m.create_row('A', ['1', 'abc'])
        self.m.delete_row('A', 0)
        self.assertEqual(len(self.m.get_table('A').rows), 0)
        self.m.delete_table('B')
        self.assertEqual([t.name for t in self.m.db.tables], ['A'])

    def test_negative_index_rejected(self):
        with self.assertRaises(ValidationError):
            self.m.delete_column('A', -1)

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.m = Manager()
        self.m.create_database('Тестова база')
        self.m.create_table('T')
        for column in (Column('i', 'integer'), Column('r', 'real'), Column('c', 'char'),
                       Column('s', 'string'), Column('interval_char', 'charInvl', 'a', 'm'),
                       Column('bounded', 'string(charInvl)', 'a', 'z')):
            self.m.create_column('T', column)
        self.m.create_row('T', ['01', '1e0', 'ї', 'текст', 'm', 'abc'])

    def test_roundtrip_all_six_types(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            self.m.save_database(path)
            second = Manager()
            second.load_database(path)
            self.assertEqual(dumps(self.m.db), dumps(second.db))
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_invalid_import_preserves_current_database(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{"version":1}', encoding='utf-8')
            before = dumps(self.m.db)
            with self.assertRaises(ValidationError):
                self.m.load_database(path)
            self.assertEqual(dumps(self.m.db), before)

    def test_import_rejects_invalid_cell(self):
        data = json.loads(dumps(self.m.db))
        data['database']['tables'][0]['rows'][0]['values'][0] = 'abc'
        with self.assertRaises(ValidationError):
            loads(json.dumps(data))

    def test_import_rejects_wrong_structure_and_types(self):
        for value in ('{}', '[]', '{"version":true,"database":{}}', '{"version":1,"version":1}'):
            with self.assertRaises(ValidationError):
                loads(value)

    def test_import_rejects_unknown_column_type(self):
        data = json.loads(dumps(self.m.db))
        data['database']['tables'][0]['columns'][0]['kind'] = 'email'
        with self.assertRaises(ValidationError):
            loads(json.dumps(data))

if __name__ == '__main__':
    unittest.main(verbosity=2)
