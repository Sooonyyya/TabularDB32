"""Веб версія"""
from pathlib import Path
import os
import secrets
import threading
from flask import Flask, render_template, request, session, redirect, url_for, flash, Response, abort
from core.manager import Manager
from core.models import Column
from core.data_types import TYPE_NAMES, ValidationError
from core.storage import loads, dumps, load_database, save_database

def create_app(storage_path=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=16*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    path = Path(storage_path or os.environ.get('TABULAR_DB_PATH', Path(__file__).parent / 'instance' / 'database.json'))
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.RLock()
    if not path.exists():
        save_database(Manager().db, path)

    def read_manager():
        return Manager(load_database(path))

    def token():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        return session['csrf']

    app.jinja_env.globals['csrf_token'] = token

    @app.before_request
    def protect():
        if request.method == 'POST':
            expected = session.get('csrf', '')
            if not expected or not secrets.compare_digest(expected, request.form.get('csrf', '')):
                abort(400, description='Форма застаріла. Оновіть сторінку й повторіть дію.')

    @app.get('/')
    def index():
        with lock:
            manager = read_manager()
        selected = request.args.get('table')
        table = next((t for t in manager.db.tables if t.name == selected), None)
        if table is None and manager.db.tables:
            table = manager.db.tables[0]
        edit = None
        row_index = request.args.get('edit', type=int)
        if table and row_index is not None and 0 <= row_index < len(table.rows):
            edit = (row_index, table.rows[row_index])
        column_index = request.args.get('column', type=int)
        column_edit = None
        if table and column_index is not None and 0 <= column_index < len(table.columns):
            column_edit = (column_index, table.columns[column_index])
        return render_template('index.html', db=manager.db, table=table,
                               types=TYPE_NAMES, edit=edit, column_edit=column_edit)

    @app.post('/action')
    def action():
        selected = request.form.get('table')
        try:
            with lock:
                manager = read_manager()
                f = request.form
                op = f.get('op', '')
                if op == 'new_db':
                    manager.create_database(f.get('name', ''))
                    selected = None
                elif op == 'import':
                    upload = request.files.get('file')
                    if not upload or not upload.filename:
                        raise ValidationError('Оберіть JSON-файл.')
                    manager.db = loads(upload.read().decode('utf-8'))
                    selected = None
                elif op == 'create_table':
                    selected = manager.create_table(f.get('name', '')).name
                elif op == 'delete_table':
                    manager.delete_table(selected)
                    selected = None
                elif op in ('create_column', 'edit_column'):
                    bounded = f.get('kind') == 'string(charInvl)'
                    col = Column(f.get('name', ''), f.get('kind', ''),
                                 f.get('lower', '') if bounded else None,
                                 f.get('upper', '') if bounded else None)
                    if op == 'create_column':
                        manager.create_column(selected, col, f.get('initial', ''))
                    else:
                        manager.edit_column(selected, int(f['index']), col)
                elif op == 'delete_column':
                    manager.delete_column(selected, int(f['index']))
                elif op in ('create_row', 'edit_row'):
                    table = manager.get_table(selected)
                    values = [f.get(f'value_{i}', '') for i in range(len(table.columns))]
                    if op == 'create_row':
                        manager.create_row(selected, values)
                    else:
                        manager.edit_row(selected, int(f['index']), values)
                elif op == 'delete_row':
                    manager.delete_row(selected, int(f['index']))
                elif op == 'union':
                    selected = manager.union_tables(f.get('first'), f.get('second'), f.get('result', '')).name
                else:
                    raise ValidationError('Невідома операція.')
                save_database(manager.db, path)
            flash('Операцію виконано. Базу збережено на сервері.', 'success')
        except (ValidationError, ValueError, OSError, KeyError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('index', table=selected), code=303)

    @app.get('/export')
    def export():
        with lock:
            database = read_manager().db
        return Response(dumps(database), mimetype='application/json',
                        headers={'Content-Disposition': 'attachment; filename="database.json"'})

    @app.errorhandler(413)
    def too_large(error):
        return 'Файл завеликий. Ліміт HTTP-завантаження: 16 МіБ.', 413

    return app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
