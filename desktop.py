"""Десктопна версія у стилі вебінтерфейсу."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.manager import Manager
from core.models import Column
from core.data_types import TYPE_NAMES, ValidationError


# Палітра взята з вебверсії (static/style.css)
BG = '#f3f5f8'
HEADER = '#152e4b'
HEADER_MUTED = '#c4d5e7'
EYEBROW = '#b7d8fa'
PANEL = '#ffffff'
BORDER = '#dce3eb'
TEXT = '#18263a'
MUTED = '#53677e'
PRIMARY = '#1764a2'
PRIMARY_HOVER = '#0a487c'
DANGER_BG = '#fff0f0'
DANGER_TEXT = '#a82929'
DANGER_HOVER = '#fbdada'
SUCCESS_BG = '#e4f3eb'
SUCCESS_TEXT = '#1a5f3f'
ERROR_BG = '#ffe8e8'
ERROR_TEXT = '#922323'
TABLE_HEAD = '#f0f4f9'
SELECTION = '#e8f1fb'


class Form(tk.Toplevel):
    def __init__(self, parent, title, fields, submit, disabled_fields=()):
        super().__init__(parent)
        self.title(title)
        self.geometry('650x520')
        self.minsize(540, 390)
        self.configure(bg=BG)
        self.transient(parent)
        self.submit = submit
        self.vars = {}
        self.widgets = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=HEADER, height=74)
        header.grid(row=0, column=0, sticky='ew')
        header.grid_propagate(False)
        tk.Label(
            header, text=title, bg=HEADER, fg='white',
            font=('Arial', 17, 'bold')
        ).pack(anchor='w', padx=24, pady=22)

        panel = tk.Frame(self, bg=PANEL, highlightbackground=BORDER,
                         highlightthickness=1)
        panel.grid(row=1, column=0, sticky='nsew', padx=22, pady=22)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)

        canvas = tk.Canvas(panel, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(panel, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky='nsew', padx=(20, 0), pady=16)
        scroll.grid(row=0, column=1, sticky='ns', padx=(0, 12), pady=16)

        body = tk.Frame(canvas, bg=PANEL)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        body.columnconfigure(0, weight=1)

        for i, (key, label, value, choices) in enumerate(fields):
            tk.Label(
                body, text=label, bg=PANEL, fg=TEXT,
                font=('Arial', 10, 'bold'), anchor='w', justify='left',
                wraplength=560
            ).grid(row=2*i, column=0, sticky='ew', pady=(10, 5))

            var = tk.StringVar(value=value)
            self.vars[key] = var
            if choices:
                widget = ttk.Combobox(
                    body, textvariable=var, values=choices,
                    state='readonly', style='Web.TCombobox'
                )
            else:
                widget = ttk.Entry(body, textvariable=var, style='Web.TEntry')
            widget.grid(row=2*i+1, column=0, sticky='ew', ipady=5)
            self.widgets[key] = widget
            if key in disabled_fields:
                widget.state(['disabled'])

        # Межі потрібні тільки для інтервальних типів:
        # charInvl (один символ у межах) і string(charInvl) (рядок із символів у межах).
        if {'kind', 'lower', 'upper'}.issubset(self.vars):
            self.vars['kind'].trace_add('write', self._toggle_bounds)
            self._toggle_bounds()

        footer = tk.Frame(self, bg=BG)
        footer.grid(row=2, column=0, sticky='ew', padx=22, pady=(0, 20))
        footer.columnconfigure(0, weight=1)

        self.error = tk.Label(
            footer, text='', bg=BG, fg=ERROR_TEXT,
            font=('Arial', 10), anchor='w', justify='left', wraplength=390
        )
        self.error.grid(row=0, column=0, sticky='w')

        buttons = tk.Frame(footer, bg=BG)
        buttons.grid(row=0, column=1, sticky='e')
        ttk.Button(buttons, text='Скасувати', style='Secondary.TButton',
                   command=self.destroy).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Застосувати', style='Primary.TButton',
                   command=self.apply).pack(side='left')

        self.grab_set()
        self.focus_force()


    def _toggle_bounds(self, *_):
        kind = self.vars.get('kind').get() if self.vars.get('kind') else ''
        active = kind in ('charInvl', 'string(charInvl)')
        for key in ('lower', 'upper'):
            widget = self.widgets.get(key)
            if widget is not None:
                if active:
                    widget.state(['!disabled'])
                else:
                    widget.state(['disabled'])

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
        self.geometry('1320x820')
        self.minsize(980, 650)
        self.configure(bg=BG)

        self.manager = Manager()
        self.path = None
        self.dirty = False
        self.current = None
        # Після запуску активної бази немає.
        # Спочатку користувач має створити нову базу або відкрити JSON.
        self.db_ready = False

        self.setup_styles()
        self.build_ui()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Arial', 10))

        style.configure(
            'Primary.TButton', font=('Arial', 10),
            padding=(14, 9), background=PRIMARY, foreground='white',
            bordercolor=PRIMARY, lightcolor=PRIMARY, darkcolor=PRIMARY
        )
        style.map(
            'Primary.TButton',
            background=[('active', PRIMARY_HOVER), ('pressed', PRIMARY_HOVER)],
            bordercolor=[('active', PRIMARY_HOVER), ('pressed', PRIMARY_HOVER)]
        )

        style.configure(
            'Secondary.TButton', font=('Arial', 10),
            padding=(12, 8), background='#ffffff', foreground=TEXT,
            bordercolor='#bdc9d7', lightcolor='#ffffff', darkcolor='#ffffff'
        )
        style.map('Secondary.TButton', background=[('active', '#eef3f8')])

        style.configure(
            'Danger.TButton', font=('Arial', 10),
            padding=(12, 8), background=DANGER_BG, foreground=DANGER_TEXT,
            bordercolor='#efcaca', lightcolor=DANGER_BG, darkcolor=DANGER_BG
        )
        style.map(
            'Danger.TButton',
            background=[('active', DANGER_HOVER), ('pressed', DANGER_HOVER)]
        )

        style.configure(
            'Web.Treeview', rowheight=34, background='white',
            fieldbackground='white', foreground=TEXT, bordercolor=BORDER,
            lightcolor=BORDER, darkcolor=BORDER
        )
        style.map(
            'Web.Treeview',
            background=[('selected', SELECTION)],
            foreground=[('selected', TEXT)]
        )
        style.configure(
            'Web.Treeview.Heading', font=('Arial', 10, 'bold'),
            background=TABLE_HEAD, foreground=TEXT, padding=(8, 8),
            bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER
        )
        style.map('Web.Treeview.Heading', background=[('active', '#e6ecf3')])

        style.configure(
            'Web.TCombobox', padding=(8, 7), fieldbackground='white',
            background='white', foreground=TEXT, bordercolor='#bdc9d7',
            arrowcolor=TEXT
        )
        style.configure(
            'Web.TEntry', padding=(8, 7), fieldbackground='white',
            foreground=TEXT, bordercolor='#bdc9d7'
        )

    def panel(self, parent, **grid):
        frame = tk.Frame(
            parent, bg=PANEL, highlightbackground=BORDER,
            highlightthickness=1
        )
        frame.grid(**grid)
        return frame

    def build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Верхня шапка, як у вебверсії
        header = tk.Frame(self, bg=HEADER)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)

        title_box = tk.Frame(header, bg=HEADER)
        title_box.grid(row=0, column=0, sticky='w', padx=36, pady=24)
        tk.Label(
            title_box, text='СИСТЕМА ТИПУ 1 · ВАРІАНТ 3–2',
            bg=HEADER, fg=EYEBROW, font=('Arial', 9, 'bold')
        ).pack(anchor='w')
        self.heading = tk.Label(
            title_box, text='', bg=HEADER, fg='white',
            font=('Arial', 23, 'bold')
        )
        self.heading.pack(anchor='w', pady=(5, 2))
        tk.Label(
            title_box, text='Таблиці, типи даних та об’єднання без повторів',
            bg=HEADER, fg=HEADER_MUTED, font=('Arial', 10)
        ).pack(anchor='w')

        self.header_save_button = ttk.Button(
            header, text='Зберегти JSON', style='Primary.TButton',
            command=self.save
        )
        self.header_save_button.grid(row=0, column=1, sticky='e', padx=36)

        # Панель глобальних дій
        toolbar = tk.Frame(self, bg=BG)
        toolbar.grid(row=1, column=0, sticky='ew', padx=30, pady=(18, 4))
        self.toolbar_buttons = {}
        for label, command in [
            ('Нова база', self.new_database),
            ('Відкрити JSON', self.open_database),
            ('Зберегти', self.save),
            ('Зберегти як', lambda: self.save(True)),
        ]:
            button = ttk.Button(toolbar, text=label, style='Secondary.TButton', command=command)
            button.pack(side='left', padx=(0, 8))
            self.toolbar_buttons[label] = button

        content = tk.Frame(self, bg=BG)
        content.grid(row=2, column=0, sticky='nsew', padx=30, pady=16)
        content.columnconfigure(0, minsize=280)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Ліва панель
        left = self.panel(content, row=0, column=0, sticky='nsew', padx=(0, 18))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        tk.Label(
            left, text='Таблиці', bg=PANEL, fg=TEXT,
            font=('Arial', 15, 'bold')
        ).grid(row=0, column=0, sticky='w', padx=20, pady=(20, 4))
        self.table_count = tk.Label(
            left, text='', bg=PANEL, fg=MUTED, font=('Arial', 9)
        )
        self.table_count.grid(row=1, column=0, sticky='w', padx=20, pady=(0, 10))

        list_frame = tk.Frame(left, bg=PANEL)
        list_frame.grid(row=2, column=0, sticky='nsew', padx=20)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tables = tk.Listbox(
            list_frame, font=('Arial', 11), exportselection=False,
            bd=0, highlightthickness=1, highlightbackground=BORDER,
            selectbackground=SELECTION, selectforeground=TEXT,
            activestyle='none', relief='flat'
        )
        self.tables.grid(row=0, column=0, sticky='nsew')
        self.tables.bind('<<ListboxSelect>>', self.select_table)
        list_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.tables.yview)
        list_scroll.grid(row=0, column=1, sticky='ns')
        self.tables.configure(yscrollcommand=list_scroll.set)

        left_actions = tk.Frame(left, bg=PANEL)
        left_actions.grid(row=3, column=0, sticky='ew', padx=20, pady=(12, 18))
        left_actions.columnconfigure(0, weight=1)
        self.create_table_button = ttk.Button(
            left_actions, text='Створити таблицю', style='Primary.TButton',
            command=self.new_table
        )
        self.create_table_button.grid(row=0, column=0, sticky='ew', pady=(0, 7))
        self.delete_table_button = ttk.Button(
            left_actions, text='Видалити таблицю', style='Danger.TButton',
            command=self.delete_table
        )
        self.delete_table_button.grid(row=1, column=0, sticky='ew')

        # Блок UNION у лівій панелі, як на вебі
        union_box = tk.Frame(left, bg=PANEL)
        union_box.grid(row=4, column=0, sticky='ew', padx=20, pady=(0, 20))
        union_box.columnconfigure(0, weight=1)
        tk.Label(
            union_box, text='Об’єднання таблиць', bg=PANEL, fg=TEXT,
            font=('Arial', 11, 'bold')
        ).grid(row=0, column=0, sticky='w', pady=(4, 8))
        tk.Label(
            union_box, text='Створює нову таблицю без повторів.',
            bg=PANEL, fg=MUTED, font=('Arial', 9), wraplength=230,
            justify='left'
        ).grid(row=1, column=0, sticky='w', pady=(0, 8))
        self.union_button = ttk.Button(
            union_box, text='Об’єднати таблиці', style='Primary.TButton',
            command=self.union_dialog
        )
        self.union_button.grid(row=2, column=0, sticky='ew')

        # Права область
        right = self.panel(content, row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        heading_row = tk.Frame(right, bg=PANEL)
        heading_row.grid(row=0, column=0, columnspan=2, sticky='ew', padx=22, pady=(20, 10))
        heading_row.columnconfigure(0, weight=1)
        self.table_heading = tk.Label(
            heading_row, text='', bg=PANEL, fg=TEXT,
            font=('Arial', 16, 'bold')
        )
        self.table_heading.grid(row=0, column=0, sticky='w')

        # Дії з рядками
        row_bar = tk.Frame(right, bg=PANEL)
        row_bar.grid(row=1, column=0, columnspan=2, sticky='ew', padx=22, pady=(0, 8))
        tk.Label(row_bar, text='Рядки', bg=PANEL, fg=MUTED,
                 font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 12))
        self.row_buttons = []
        for text, cmd, style_name in [
            ('Додати рядок', lambda: self.row_dialog(), 'Primary.TButton'),
            ('Редагувати рядок', lambda: self.row_dialog(True), 'Secondary.TButton'),
            ('Видалити рядок', self.delete_row, 'Danger.TButton')
        ]:
            button = ttk.Button(
                row_bar, text=text, style=style_name,
                command=lambda c=cmd: self.guard(c)
            )
            button.pack(side='left', padx=(0, 7))
            self.row_buttons.append(button)

        # Дії зі схемою
        schema_bar = tk.Frame(right, bg=PANEL)
        schema_bar.grid(row=2, column=0, columnspan=2, sticky='ew', padx=22, pady=(0, 12))
        tk.Label(schema_bar, text='Колонки', bg=PANEL, fg=MUTED,
                 font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 12))
        self.columns = ttk.Combobox(schema_bar, state='readonly', width=30,
                                    style='Web.TCombobox')
        self.columns.pack(side='left', padx=(0, 8))
        self.schema_buttons = []
        for text, cmd, style_name in [
            ('+ Колонка', lambda: self.column_dialog(), 'Primary.TButton'),
            ('Змінити', lambda: self.column_dialog(True), 'Secondary.TButton'),
            ('Видалити', self.delete_column, 'Danger.TButton')
        ]:
            button = ttk.Button(
                schema_bar, text=text, style=style_name,
                command=lambda c=cmd: self.guard(c)
            )
            button.pack(side='left', padx=(0, 7))
            self.schema_buttons.append(button)

        separator = tk.Frame(right, bg=BORDER, height=1)
        separator.grid(row=3, column=0, columnspan=2, sticky='ew', padx=22)

        table_frame = tk.Frame(right, bg=PANEL)
        table_frame.grid(row=4, column=0, columnspan=2, sticky='nsew', padx=22, pady=(12, 22))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.gridview = ttk.Treeview(
            table_frame, show='headings', selectmode='browse', style='Web.Treeview'
        )
        self.gridview.grid(row=0, column=0, sticky='nsew')
        self.gridview.bind('<Double-1>', lambda e: self.guard(lambda: self.row_dialog(True)))

        yscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.gridview.yview)
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.gridview.xview)
        xscroll.grid(row=1, column=0, sticky='ew')
        self.gridview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        # Повідомлення внизу
        self.status_frame = tk.Frame(self, bg=BG)
        self.status_frame.grid(row=3, column=0, sticky='ew', padx=30, pady=(0, 22))
        self.status = tk.Label(
            self.status_frame, text='Спочатку створіть нову базу або відкрийте JSON-файл.',
            bg=BG, fg=MUTED, font=('Arial', 10), anchor='w', justify='left',
            padx=14, pady=10
        )
        self.status.pack(fill='x')

    def set_status(self, text, kind='neutral'):
        if kind == 'success':
            bg, fg = SUCCESS_BG, SUCCESS_TEXT
        elif kind == 'error':
            bg, fg = ERROR_BG, ERROR_TEXT
        else:
            bg, fg = BG, MUTED
        self.status.configure(text=text, bg=bg, fg=fg)

    def ask_yes_no(self, title, message):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=BG)

        result = {'value': False}

        body = tk.Frame(
            dialog, bg=PANEL, highlightbackground=BORDER,
            highlightthickness=1
        )
        body.pack(fill='both', expand=True, padx=16, pady=16)

        tk.Label(
            body, text=message, bg=PANEL, fg=TEXT,
            font=('Arial', 11, 'bold'), wraplength=320,
            justify='center', padx=30, pady=24
        ).pack(fill='x')

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(pady=(0, 20))

        def close(value):
            result['value'] = value
            dialog.destroy()

        ttk.Button(
            buttons, text='Так', style='Primary.TButton',
            command=lambda: close(True)
        ).pack(side='left', padx=8)
        ttk.Button(
            buttons, text='Ні', style='Secondary.TButton',
            command=lambda: close(False)
        ).pack(side='left', padx=8)

        dialog.protocol('WM_DELETE_WINDOW', lambda: close(False))
        dialog.bind('<Escape>', lambda e: close(False))
        dialog.bind('<Return>', lambda e: close(True))

        dialog.update_idletasks()
        w = dialog.winfo_reqwidth()
        h = dialog.winfo_reqheight()
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dialog.geometry(f'{w}x{h}+{max(0, x)}+{max(0, y)}')

        dialog.wait_window()
        return result['value']

    def guard(self, action):
        try:
            return action()
        except (ValidationError, OSError) as exc:
            self.set_status(str(exc), 'error')

    def mutate(self, action, current=None):
        action()
        self.dirty = True
        if current is not None:
            self.current = current
        self.refresh()
        self.set_status('Зміни внесено. Збережіть базу у JSON.', 'success')

    def require_database(self):
        if not self.db_ready:
            raise ValidationError('Спочатку створіть нову базу або відкрийте JSON-файл.')

    def update_database_controls(self):
        ready = self.db_ready
        state = 'normal' if ready else 'disabled'
        self.header_save_button.configure(state=state)
        self.toolbar_buttons['Зберегти'].configure(state=state)
        self.toolbar_buttons['Зберегти як'].configure(state=state)
        self.create_table_button.configure(state=state)
        self.delete_table_button.configure(state=state if self.current else 'disabled')
        table_count = len(self.manager.db.tables) if ready and self.manager.db is not None else 0
        self.union_button.configure(state=state if ready and table_count >= 1 else 'disabled')
        self.tables.configure(state=state)
        for button in self.row_buttons:
            button.configure(state=state if ready and self.current else 'disabled')
        for button in self.schema_buttons:
            button.configure(state=state if ready and self.current else 'disabled')
        self.columns.configure(state='readonly' if ready and self.current else 'disabled')

    def refresh(self):
        title = self.manager.db.name if self.db_ready and self.manager.db is not None else 'Базу не створено'
        self.heading.configure(text=f'{title}' + (' *' if self.dirty else ''))
        names = [t.name for t in self.manager.db.tables] if self.db_ready and self.manager.db is not None else []
        self.table_count.configure(text=f'{len(names)} таблиць')

        if self.current not in names:
            self.current = names[0] if names else None

        self.tables.delete(0, 'end')
        for name in names:
            table = self.manager.get_table(name)
            self.tables.insert('end', f'{name}   ({len(table.rows)})')
        if self.current:
            self.tables.selection_set(names.index(self.current))

        self.gridview.delete(*self.gridview.get_children())
        table = self.manager.get_table(self.current) if self.current else None
        cols = [f'c{i}' for i in range(len(table.columns))] if table else []
        self.gridview.configure(columns=cols, displaycolumns=cols)

        for i, col in enumerate(table.columns if table else []):
            col_id = cols[i]
            type_text = col.kind
            if col.kind in ('charInvl', 'string(charInvl)'):
                type_text += f' [{col.lower};{col.upper}]'

            # ttk.Treeview погано відображає багаторядкові заголовки,
            # тому назву і тип показуємо в один рядок.
            header_text = f'{col.name} ({type_text})'
            width = max(120, min(260, 8 * len(header_text)))
            value_anchor = 'center' if col.kind in ('integer', 'real', 'char', 'charInvl') else 'w'
            self.gridview.heading(col_id, text=header_text, anchor='center')
            self.gridview.column(col_id, width=width, minwidth=120, stretch=True, anchor=value_anchor)

        for i, row in enumerate(table.rows if table else []):
            self.gridview.insert('', 'end', iid=str(i), values=row.values)

        self.columns['values'] = [c.label for c in table.columns] if table else []
        self.columns.set('')
        if table and table.columns:
            self.columns.current(0)

        if table:
            self.table_heading.configure(text=f'{self.current}   ·   {len(table.rows)} рядків')
        else:
            self.table_heading.configure(text='Немає таблиць' if self.db_ready else 'Спочатку створіть або відкрийте базу')

        self.update_database_controls()

    def table(self):
        self.require_database()
        if not self.current:
            raise ValidationError('Спочатку створіть або виберіть таблицю.')
        return self.manager.get_table(self.current)

    def select_table(self, event=None):
        selected = self.tables.curselection()
        if selected:
            names = [t.name for t in self.manager.db.tables]
            self.current = names[selected[0]]
            self.refresh()

    def allow_discard(self):
        return not self.dirty or self.ask_yes_no(
            'Незбережені зміни', 'Відкинути незбережені зміни?'
        )

    def close(self):
        if self.allow_discard():
            self.destroy()

    def new_database(self):
        if self.allow_discard():
            def apply(v):
                self.manager.create_database(v['name'])
                self.path = None
                self.db_ready = True
                self.current = None
                self.mutate(lambda: None)
            Form(self, 'Нова база даних', [('name', 'Назва бази', '', None)], apply)

    def open_database(self):
        if self.allow_discard():
            path = filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
            if path:
                def apply():
                    self.manager.load_database(path)
                    self.db_ready = True
                    self.path, self.dirty = path, False
                    self.current = None
                    self.refresh()
                    self.set_status(f'Завантажено: {path}', 'success')
                self.guard(apply)

    def save(self, save_as=False):
        try:
            self.require_database()
        except ValidationError as exc:
            self.set_status(str(exc), 'error')
            return
        path = self.path
        if save_as or not path:
            path = filedialog.asksaveasfilename(
                defaultextension='.json', filetypes=[('JSON', '*.json')]
            )
        if not path:
            return

        def apply():
            self.manager.save_database(path)
            self.path, self.dirty = path, False
            self.refresh()
            self.set_status(f'Збережено: {path}', 'success')
        self.guard(apply)

    def new_table(self):
        try:
            self.require_database()
        except ValidationError as exc:
            self.set_status(str(exc), 'error')
            return
        Form(
            self, 'Створити таблицю', [('name', 'Назва таблиці', '', None)],
            lambda v: self.mutate(
                lambda: self.manager.create_table(v['name']), v['name'].strip()
            )
        )

    def delete_table(self):
        def apply():
            self.table()
            if self.ask_yes_no(
                'Видалення таблиці', 'Видалити таблицю разом із рядками?'
            ):
                current = self.current
                self.mutate(lambda: self.manager.delete_table(current))
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
        fields = [
            (str(i), col.label, table.rows[index].values[i] if edit else '', None)
            for i, col in enumerate(table.columns)
        ]

        def apply(v):
            values = [v[str(i)] for i in range(len(table.columns))]
            self.mutate(
                lambda: self.manager.edit_row(table.name, index, values)
                if edit else self.manager.create_row(table.name, values)
            )
        return Form(self, 'Редагувати рядок' if edit else 'Додати рядок', fields, apply)

    def delete_row(self):
        table, index = self.table(), self.row_index()
        if self.ask_yes_no(
            'Видалення рядка', 'Видалити вибраний рядок?'
        ):
            self.mutate(lambda: self.manager.delete_row(table.name, index))

    def column_dialog(self, edit=False):
        table = self.table()
        index = self.columns.current()
        if edit:
            self.manager.index(index, len(table.columns))
        col = table.columns[index] if edit else Column('', 'string')
        fields = [
            ('name', 'Назва колонки', col.name, None),
            ('kind', 'Тип даних', col.kind, TYPE_NAMES),
            ('lower', 'Нижня межа для charInvl / string(charInvl)', col.lower or '', None),
            ('upper', 'Верхня межа для charInvl / string(charInvl)', col.upper or '', None),
        ]
        if not edit:
            fields.append((
                'initial', 'Початкове значення для вже наявних рядків', '', None
            ))

        def apply(v):
            bounded = v['kind'] in ('charInvl', 'string(charInvl)')
            column = Column(
                v['name'], v['kind'],
                v['lower'] if bounded else None,
                v['upper'] if bounded else None
            )
            self.mutate(
                lambda: self.manager.edit_column(table.name, index, column)
            if edit else self.manager.create_column(
                table.name, column, v.get('initial', '')
            )
            )

        return Form(
        self,
        'Змінити колонку' if edit else 'Додати колонку',
        fields,
        apply,
        disabled_fields=('initial',) if not edit and not table.rows else ()
        )

    def delete_column(self):
        table = self.table()
        index = self.columns.current()
        self.manager.index(index, len(table.columns))
        if self.ask_yes_no(
            'Видалення колонки', 'Видалити колонку та її значення?'
        ):
            self.mutate(lambda: self.manager.delete_column(table.name, index))

    def union_dialog(self):
        try:
            self.require_database()
        except ValidationError as exc:
            self.set_status(str(exc), 'error')
            return
        names = [t.name for t in self.manager.db.tables]
        if not names:
            self.set_status('Спочатку створіть таблиці.', 'error')
            return
        fields = [
            ('first', 'Перша таблиця', names[0], names),
            ('second', 'Друга таблиця', names[-1], names),
            ('result', 'Назва нової таблиці без повторів', 'Об’єднання', None),
        ]

        def apply(v):
            self.mutate(
                lambda: self.manager.union_tables(v['first'], v['second'], v['result']),
                v['result'].strip()
            )
        return Form(self, 'Об’єднання таблиць', fields, apply)


if __name__ == '__main__':
    Application().mainloop()
