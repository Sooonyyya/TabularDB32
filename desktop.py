"""Десктопна версія"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.manager import Manager
from core.models import Column
from core.data_types import TYPE_NAMES, ValidationError

class Form(tk.Toplevel):
    def __init__(self, parent, title, fields, submit):
        super().__init__(parent)
        self.title(title)
        self.geometry('620x490')
        self.transient(parent)
        self.submit = submit
        self.vars = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        canvas = tk.Canvas(self, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky='nsew', padx=15, pady=15)
        scroll.grid(row=0, column=1, sticky='ns')
        body = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        body.columnconfigure(0, weight=1)
        for i, (key, label, value, choices) in enumerate(fields):
            ttk.Label(body, text=label, wraplength=550).grid(row=2*i, column=0, sticky='w', pady=(8, 3))
            var = tk.StringVar(value=value)
            self.vars[key] = var
            widget = ttk.Combobox(body, textvariable=var, values=choices, state='readonly') if choices else ttk.Entry(body, textvariable=var)
            widget.grid(row=2*i+1, column=0, sticky='ew', ipady=4)
        self.error = ttk.Label(self, text='', foreground='#b42318', wraplength=570)
        self.error.grid(row=1, column=0, sticky='w', padx=15)
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky='e', padx=15, pady=15)
        ttk.Button(buttons, text='Скасувати', command=self.destroy).pack(side='left', padx=5)
        ttk.Button(buttons, text='Застосувати', command=self.apply).pack(side='left')
        self.grab_set()

    def apply(self):
        try:
            self.submit({key: var.get() for key, var in self.vars.items()})
            self.destroy()
        except (ValidationError, OSError) as exc:
            self.error.configure(text=str(exc))

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Таблична база даних • Варіант 3–2')
        self.geometry('1160x730')
        self.minsize(850, 560)
        self.manager = Manager()
        self.path = None
        self.dirty = False
        self.current = None
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Arial', 11))
        style.configure('Treeview', rowheight=30)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
        style.configure('TButton', padding=(8, 6))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.heading = ttk.Label(self, font=('Arial', 19, 'bold'))
        self.heading.grid(row=0, column=0, sticky='w', padx=20, pady=(18, 10))
        top = ttk.Frame(self)
        top.grid(row=1, column=0, sticky='ew', padx=15, pady=5)
        for label, command in [('Нова база', self.new_database), ('Відкрити JSON', self.open_database),
                               ('Зберегти', self.save), ('Зберегти як', lambda: self.save(True)),
                               ('Об’єднати таблиці', self.union_dialog)]:
            ttk.Button(top, text=label, command=command).pack(side='left', padx=4)
        panes = ttk.Panedwindow(self, orient='horizontal')
        panes.grid(row=2, column=0, sticky='nsew', padx=20, pady=10)
        left = ttk.Frame(panes)
        panes.add(left, weight=1)
        ttk.Label(left, text='Таблиці', font=('Arial', 13, 'bold')).pack(anchor='w', pady=6)
        self.tables = tk.Listbox(left, font=('Arial', 12), exportselection=False, width=22)
        self.tables.pack(fill='both', expand=True)
        self.tables.bind('<<ListboxSelect>>', self.select_table)
        ttk.Button(left, text='Створити таблицю', command=self.new_table).pack(fill='x', pady=(8, 4))
        ttk.Button(left, text='Видалити таблицю', command=self.delete_table).pack(fill='x')
        right = ttk.Frame(panes)
        panes.add(right, weight=5)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        self.table_heading = ttk.Label(right, font=('Arial', 13, 'bold'))
        self.table_heading.grid(row=0, column=0, sticky='w', pady=6)
        bar = ttk.Frame(right)
        bar.grid(row=1, column=0, sticky='w', pady=4)
        for text, cmd in [('Додати рядок', lambda: self.row_dialog()), ('Редагувати рядок', lambda: self.row_dialog(True)), ('Видалити рядок', self.delete_row)]:
            ttk.Button(bar, text=text, command=lambda c=cmd: self.guard(c)).pack(side='left', padx=2)
        schema_bar = ttk.Frame(right)
        schema_bar.grid(row=2, column=0, sticky='ew', pady=6)
        self.columns = ttk.Combobox(schema_bar, state='readonly', width=28)
        self.columns.pack(side='left', padx=2)
        for text, cmd in [('+ Колонка', lambda: self.column_dialog()), ('Змінити', lambda: self.column_dialog(True)), ('Видалити', self.delete_column)]:
            ttk.Button(schema_bar, text=text, command=lambda c=cmd: self.guard(c)).pack(side='left', padx=2)
        self.gridview = ttk.Treeview(right, show='headings', selectmode='browse')
        self.gridview.grid(row=3, column=0, sticky='nsew')
        self.gridview.bind('<Double-1>', lambda e: self.guard(lambda: self.row_dialog(True)))
        yscroll = ttk.Scrollbar(right, orient='vertical', command=self.gridview.yview)
        yscroll.grid(row=3, column=1, sticky='ns')
        xscroll = ttk.Scrollbar(right, orient='horizontal', command=self.gridview.xview)
        xscroll.grid(row=4, column=0, sticky='ew')
        self.gridview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.status = ttk.Label(self, text='Створіть таблицю або відкрийте JSON.', wraplength=1100)
        self.status.grid(row=3, column=0, sticky='w', padx=20, pady=(5, 18))
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def guard(self, action):
        try:
            return action()
        except (ValidationError, OSError) as exc:
            self.status.configure(text=str(exc), foreground='#b42318')

    def mutate(self, action, current=None):
        action()
        self.dirty = True
        if current is not None:
            self.current = current
        self.refresh()
        self.status.configure(text='Зміни внесено. Збережіть базу у JSON.', foreground='#14643e')

    def refresh(self):
        self.heading.configure(text=f'{self.manager.db.name}' + (' *' if self.dirty else ''))
        names = [t.name for t in self.manager.db.tables]
        if self.current not in names:
            self.current = names[0] if names else None
        self.tables.delete(0, 'end')
        for name in names:
            self.tables.insert('end', name)
        if self.current:
            self.tables.selection_set(names.index(self.current))
        self.gridview.delete(*self.gridview.get_children())
        table = self.manager.get_table(self.current) if self.current else None
        cols = [str(i) for i in range(len(table.columns))] if table else []
        self.gridview.configure(columns=cols)
        for i, col in enumerate(table.columns if table else []):
            self.gridview.heading(str(i), text=col.name)
            self.gridview.column(str(i), width=145, minwidth=100, stretch=False)
        for i, row in enumerate(table.rows if table else []):
            self.gridview.insert('', 'end', iid=str(i), values=row.values)
        self.columns['values'] = [c.label for c in table.columns] if table else []
        self.columns.set('')
        if table and table.columns:
            self.columns.current(0)
        self.table_heading.configure(text=f'{self.current} • {len(table.rows)} рядків' if table else 'Немає таблиць')

    def table(self):
        if not self.current:
            raise ValidationError('Спочатку створіть або виберіть таблицю.')
        return self.manager.get_table(self.current)

    def select_table(self, event=None):
        selected = self.tables.curselection()
        if selected:
            self.current = self.tables.get(selected[0])
            self.refresh()

    def allow_discard(self):
        return not self.dirty or messagebox.askyesno('Незбережені зміни', 'Відкинути незбережені зміни?', parent=self)

    def close(self):
        if self.allow_discard():
            self.destroy()

    def new_database(self):
        if self.allow_discard():
            def apply(v):
                self.manager.create_database(v['name'])
                self.path = None
                self.mutate(lambda: None)
            Form(self, 'Нова база даних', [('name', 'Назва бази', '', None)], apply)

    def open_database(self):
        if self.allow_discard():
            path = filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
            if path:
                def apply():
                    self.manager.load_database(path)
                    self.path, self.dirty = path, False
                    self.refresh()
                    self.status.configure(text=f'Завантажено: {path}', foreground='#14643e')
                self.guard(apply)

    def save(self, save_as=False):
        path = self.path
        if save_as or not path:
            path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')])
        if not path:
            return
        def apply():
            self.manager.save_database(path)
            self.path, self.dirty = path, False
            self.refresh()
            self.status.configure(text=f'Збережено: {path}', foreground='#14643e')
        self.guard(apply)

    def new_table(self):
        Form(self, 'Створити таблицю', [('name', 'Назва таблиці', '', None)],
             lambda v: self.mutate(lambda: self.manager.create_table(v['name']), v['name'].strip()))

    def delete_table(self):
        def apply():
            self.table()
            if messagebox.askyesno('Видалення таблиці', 'Видалити таблицю разом із рядками?', parent=self):
                self.mutate(lambda: self.manager.delete_table(self.current))
        self.guard(apply)

    def row_index(self):
        selected = self.gridview.selection()
        if not selected:
            raise ValidationError('Оберіть рядок таблиці.')
        return int(selected[0])

    def row_dialog(self, edit=False):
        table = self.table()
        if not table.columns:
            raise ValidationError('Спочатку додайте колонки.')
        index = self.row_index() if edit else None
        fields = [(str(i), col.label, table.rows[index].values[i] if edit else '', None)
                  for i, col in enumerate(table.columns)]
        def apply(v):
            values = [v[str(i)] for i in range(len(table.columns))]
            self.mutate(lambda: self.manager.edit_row(table.name, index, values) if edit
                        else self.manager.create_row(table.name, values))
        return Form(self, 'Редагувати рядок' if edit else 'Додати рядок', fields, apply)

    def delete_row(self):
        table, index = self.table(), self.row_index()
        if messagebox.askyesno('Видалення рядка', 'Видалити вибраний рядок?', parent=self):
            self.mutate(lambda: self.manager.delete_row(table.name, index))

    def column_dialog(self, edit=False):
        table = self.table()
        index = self.columns.current()
        if edit:
            self.manager.index(index, len(table.columns))
        col = table.columns[index] if edit else Column('', 'string')
        fields = [('name', 'Назва колонки', col.name, None),
                  ('kind', 'Тип даних', col.kind, TYPE_NAMES),
                  ('lower', 'Нижня межа тільки для string(charInvl)', col.lower or '', None),
                  ('upper', 'Верхня межа тільки для string(charInvl)', col.upper or '', None)]
        if not edit:
            fields.append(('initial', 'Початкове значення для вже наявних рядків', '', None))
        def apply(v):
            bounded = v['kind'] == 'string(charInvl)'
            column = Column(v['name'], v['kind'], v['lower'] if bounded else None, v['upper'] if bounded else None)
            self.mutate(lambda: self.manager.edit_column(table.name, index, column) if edit
                        else self.manager.create_column(table.name, column, v['initial']))
        return Form(self, 'Змінити колонку' if edit else 'Додати колонку', fields, apply)

    def delete_column(self):
        table = self.table()
        index = self.columns.current()
        self.manager.index(index, len(table.columns))
        if messagebox.askyesno('Видалення колонки', 'Видалити колонку та її значення?', parent=self):
            self.mutate(lambda: self.manager.delete_column(table.name, index))

    def union_dialog(self):
        names = [t.name for t in self.manager.db.tables]
        if not names:
            self.status.configure(text='Спочатку створіть таблиці.', foreground='#b42318')
            return
        fields = [('first', 'Перша таблиця', names[0], names),
                  ('second', 'Друга таблиця', names[-1], names),
                  ('result', 'Назва нової таблиці без повторів', 'Об’єднання', None)]
        def apply(v):
            self.mutate(lambda: self.manager.union_tables(v['first'], v['second'], v['result']), v['result'].strip())
        return Form(self, 'Об’єднання таблиць', fields, apply)

if __name__ == '__main__':
    Application().mainloop()
