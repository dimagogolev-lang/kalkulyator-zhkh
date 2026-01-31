# -*- coding: utf-8 -*-
"""
Калькулятор коммунальных платежей (ХВС, ГВС, свет день/ночь).
Логика расчётов как в Excel. Тарифы в config.json, история — в history.json.
"""
import json
import os
import sys
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

from calc import calculate

# Путь к данным: рядом с exe или рядом со скриптом
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
HISTORY_PATH = os.path.join(BASE_DIR, "history.json")

MONTHS_RU = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
)

DEFAULT_TARIFFS = {
    "tariff_sewage": 46.73,
    "tariff_xvs": 43.24,
    "tariff_gvs": 43.24,
    "tariff_heating_per_gcal": 2891.74,
    "norm_gcal_per_m3": 0.06,
    "tariff_el_day": 6.79,
    "tariff_el_night": 2.81,
}


def load_config():
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_TARIFFS)


def save_config(tariffs):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(tariffs, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_history():
    if os.path.isfile(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(records):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def default_period_name():
    now = datetime.now()
    return f"{MONTHS_RU[now.month - 1]} {now.year}"


def parse_float(s, default=None):
    s = (s or "").strip().replace(",", ".")
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return None


# Стиль в духе Apple: светлый фон, аккуратная типографика
BG_MAIN = "#f5f5f7"
BG_CARD = "#ffffff"
ACCENT = "#007AFF"
TEXT = "#1d1d1f"
TEXT_SECONDARY = "#6e6e73"
FONT_UI = "Segoe UI"
FONT_SIZE = 10
FONT_HEAD = 11


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Калькулятор ЖКХ")
        self.root.geometry("580x620")
        self.root.resizable(True, True)
        self.root.minsize(420, 480)
        self.root.configure(bg=BG_MAIN)
        self._setup_style()

        self.config = load_config()
        if not os.path.isfile(CONFIG_PATH):
            save_config(self.config)
        self._last_result = None
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG_MAIN, foreground=TEXT, font=(FONT_UI, FONT_SIZE))
        style.configure("TFrame", background=BG_MAIN)
        style.configure("TLabel", background=BG_MAIN, foreground=TEXT, font=(FONT_UI, FONT_SIZE))
        style.configure("TLabelframe", background=BG_MAIN)
        style.configure("TLabelframe.Label", background=BG_MAIN, font=(FONT_UI, FONT_HEAD))
        style.configure("TButton", padding=(16, 10), font=(FONT_UI, FONT_SIZE))
        style.map("TButton", background=[("active", "#e5e5ea")])
        style.configure("TEntry", padding=8, font=(FONT_UI, FONT_SIZE))

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=(24, 20))
        main.pack(fill=tk.BOTH, expand=True)

        # --- Периоды (хронология) ---
        self._timeline_records = []
        row_top = 0
        lf_timeline = ttk.LabelFrame(main, text="Периоды  ·  клик — подставить в «предыдущие»  ·  ПКМ — удалить")
        lf_timeline.grid(row=row_top, column=0, columnspan=5, sticky=tk.EW, pady=(0, 16))
        lf_timeline.columnconfigure(0, weight=1)
        inner = ttk.Frame(lf_timeline, padding=12)
        inner.grid(row=0, column=0, sticky=tk.EW)
        inner.columnconfigure(0, weight=1)
        list_frame = ttk.Frame(inner)
        list_frame.grid(row=0, column=0, sticky=tk.EW)
        list_frame.columnconfigure(0, weight=1)
        self._timeline_listbox = tk.Listbox(
            list_frame, height=4, font=(FONT_UI, FONT_SIZE),
            bg=BG_CARD, fg=TEXT, selectbackground=ACCENT, selectforeground="white",
            relief=tk.FLAT, highlightthickness=0
        )
        scroll_t = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._timeline_listbox.yview)
        self._timeline_listbox.configure(yscrollcommand=scroll_t.set)
        self._timeline_listbox.grid(row=0, column=0, sticky=tk.NSEW)
        scroll_t.grid(row=0, column=1, sticky=tk.NS)
        list_frame.columnconfigure(0, weight=1)
        self._timeline_listbox.bind("<<ListboxSelect>>", self._on_timeline_select)
        self._timeline_listbox.bind("<Button-3>", self._on_timeline_rightclick)
        self._analytics_label = tk.Label(
            inner, text="", font=(FONT_UI, FONT_SIZE), fg=TEXT_SECONDARY, bg=BG_MAIN, anchor=tk.CENTER
        )
        self._analytics_label.grid(row=1, column=0, sticky=tk.EW, pady=(12, 0))
        inner.columnconfigure(0, weight=1)
        self._refresh_timeline()

        # --- Показания ---
        row_start = row_top + 1
        for col, text in [(1, "Предыдущие показания"), (3, "Текущие показания")]:
            lbl = tk.Label(main, text=text, font=(FONT_UI, FONT_HEAD, "bold"), fg=TEXT, bg=BG_MAIN, anchor=tk.CENTER)
            lbl.grid(row=row_start + 0, column=col, columnspan=2, pady=(0, 6), sticky=tk.EW)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(3, weight=1)

        labels = [
            ("ХВС (холодная вода), м³", "xvs_prev", "xvs_curr"),
            ("ГВС (горячая вода), м³", "gvs_prev", "gvs_curr"),
            ("Электричество день, кВт·ч", "el_day_prev", "el_day_curr"),
            ("Электричество ночь, кВт·ч", "el_night_prev", "el_night_curr"),
        ]
        self.entries = {}
        for i, (text, key_prev, key_curr) in enumerate(labels):
            row = row_start + i + 1
            ttk.Label(main, text=text).grid(row=row, column=0, sticky=tk.W, pady=6)
            self.entries[key_prev] = ttk.Entry(main, width=14)
            self.entries[key_prev].grid(row=row, column=1, padx=6, pady=6)
            self.entries[key_curr] = ttk.Entry(main, width=14)
            self.entries[key_curr].grid(row=row, column=3, padx=6, pady=6)

        ttk.Separator(main, orient=tk.HORIZONTAL).grid(
            row=row_start + 5, column=0, columnspan=5, sticky=tk.EW, pady=20
        )

        # --- Кнопки расчёта и сохранения ---
        row_btns = row_start + 6
        btn_calc = ttk.Button(main, text="Рассчитать", command=self._on_calc)
        btn_calc.grid(row=row_btns, column=0, columnspan=3, pady=10, padx=(0, 6))
        self.btn_save_history = ttk.Button(
            main, text="Сохранить в историю", command=self._save_to_history, state=tk.DISABLED
        )
        self.btn_save_history.grid(row=row_btns, column=3, columnspan=2, pady=10, padx=6)

        # --- Результаты ---
        self.result_frame = ttk.LabelFrame(main, text="Результат", padding=16)
        self.result_frame.grid(row=row_start + 7, column=0, columnspan=5, sticky=tk.EW, pady=10)
        self.result_text = tk.Text(
            self.result_frame, height=11, width=50, wrap=tk.WORD,
            font=(FONT_UI, FONT_SIZE), bg=BG_CARD, fg=TEXT, relief=tk.FLAT, padx=12, pady=12
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.config(state=tk.DISABLED)

        # --- Нижние кнопки ---
        ttk.Button(main, text="История по месяцам", command=self._show_history).grid(
            row=row_start + 8, column=0, columnspan=2, pady=12, padx=(0, 6))
        ttk.Button(main, text="Тарифы", command=self._edit_tariffs).grid(
            row=row_start + 8, column=2, columnspan=3, pady=12, padx=6)

        self._fill_previous_from_latest()

        for c in (0, 1, 2, 3):
            main.columnconfigure(c, weight=0)
        main.columnconfigure(4, weight=1)

    def _get_inputs(self):
        out = {}
        for key in (
            "xvs_prev", "xvs_curr", "gvs_prev", "gvs_curr",
            "el_day_prev", "el_day_curr", "el_night_prev", "el_night_curr",
        ):
            val = parse_float(self.entries[key].get())
            if val is None:
                return None, key
            out[key] = val
        return out, None

    def _refresh_timeline(self):
        records = load_history()
        self._timeline_records = sorted(records, key=lambda r: r.get("date_saved", ""))
        self._timeline_listbox.delete(0, tk.END)
        total_sum = 0
        for r in self._timeline_records:
            total_sum += r.get("total", 0)
            period = r.get("period", "—")
            total = r.get("total", 0)
            self._timeline_listbox.insert(tk.END, f"  {period}  —  {total:,.2f} руб".replace(",", " "))
        n = len(self._timeline_records)
        if n == 0:
            self._analytics_label.config(text="Нет сохранённых периодов. После расчёта нажмите «Сохранить в историю».")
        else:
            avg = total_sum / n
            last_period = self._timeline_records[-1].get("period", "—") if self._timeline_records else "—"
            self._analytics_label.config(
                text=f"Всего за {n} мес.: {total_sum:,.2f} руб  |  В среднем: {avg:,.2f} руб/мес.  |  Последний период: {last_period}".replace(",", " ")
            )

    def _on_timeline_select(self, event):
        sel = self._timeline_listbox.curselection()
        if not sel or sel[0] >= len(self._timeline_records):
            return
        r = self._timeline_records[sel[0]]
        for key, attr in [
            ("xvs_prev", "xvs_curr"), ("gvs_prev", "gvs_curr"),
            ("el_day_prev", "el_day_curr"), ("el_night_prev", "el_night_curr"),
        ]:
            val = r.get(attr)
            if val is not None:
                self.entries[key].delete(0, tk.END)
                self.entries[key].insert(0, str(val))
            else:
                if key == "xvs_prev":
                    messagebox.showinfo(
                        "Периоды",
                        "В этой записи нет показаний для подстановки (сохранена до обновления программы).",
                    )
                break

    def _fill_previous_from_latest(self):
        if not self._timeline_records:
            return
        r = self._timeline_records[-1]
        if r.get("xvs_curr") is None:
            return
        for key, attr in [
            ("xvs_prev", "xvs_curr"), ("gvs_prev", "gvs_curr"),
            ("el_day_prev", "el_day_curr"), ("el_night_prev", "el_night_curr"),
        ]:
            val = r.get(attr)
            if val is not None:
                self.entries[key].delete(0, tk.END)
                self.entries[key].insert(0, str(val))

    def _on_timeline_rightclick(self, event):
        sel = self._timeline_listbox.curselection()
        if not sel or sel[0] >= len(self._timeline_records):
            return
        idx = sel[0]
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Удалить запись", command=lambda: self._delete_timeline_record(idx))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_timeline_record(self, listbox_index):
        if listbox_index >= len(self._timeline_records):
            return
        r = self._timeline_records[listbox_index]
        period = r.get("period", "")
        if not messagebox.askyesno("Удалить запись", f"Удалить период «{period}» из истории?"):
            return
        records = load_history()
        key = (r.get("period"), r.get("date_saved"))
        records = [x for x in records if (x.get("period"), x.get("date_saved")) != key]
        if save_history(records):
            self._refresh_timeline()
            messagebox.showinfo("История", "Запись удалена.")
        else:
            messagebox.showwarning("История", "Не удалось сохранить изменения.")

    def _on_calc(self):
        inputs, missing = self._get_inputs()
        if inputs is None:
            messagebox.showwarning(
                "Ввод",
                "Заполните все поля показаний числами.\nНе найдено значение для одного из полей.",
            )
            return
        if any(inputs[k] < 0 for k in inputs):
            messagebox.showwarning("Ввод", "Показания не могут быть отрицательными.")
            return
        if inputs["xvs_curr"] < inputs["xvs_prev"] or inputs["gvs_curr"] < inputs["gvs_prev"]:
            messagebox.showwarning("Ввод", "Текущие показания воды должны быть не меньше предыдущих.")
            return
        if inputs["el_day_curr"] < inputs["el_day_prev"] or inputs["el_night_curr"] < inputs["el_night_prev"]:
            messagebox.showwarning("Ввод", "Текущие показания электричества должны быть не меньше предыдущих.")
            return

        tariffs = {k: self.config.get(k, v) for k, v in DEFAULT_TARIFFS.items()}
        result = calculate(**inputs, **tariffs)

        cons = result["consumption"]
        lines = [
            "Расход: ХВС {:.2f} м³, ГВС {:.2f} м³ | эл. день {:.2f}, ночь {:.2f} кВт·ч".format(
                cons["xvs"], cons["gvs"], cons["el_day"], cons["el_night"]
            ),
            "",
            "——— Вода ———",
            f"  Водоотведение:     {result['sum_sewage']:.2f} руб",
            f"  ХВС:               {result['sum_xvs']:.2f} руб",
            f"  Подогрев ГВС:      {result['sum_heating']:.2f} руб",
            f"  ГВС:               {result['sum_gvs']:.2f} руб",
            f"  Итого за воду:     {result['sum_water']:.2f} руб",
            "",
            "——— Электричество ———",
            f"  День:              {result['sum_el_day']:.2f} руб",
            f"  Ночь:              {result['sum_el_night']:.2f} руб",
            f"  Итого за свет:     {result['sum_electricity']:.2f} руб",
            "",
            "═══════════════════════",
            f"  ИТОГО (свет+вода): {result['total']:.2f} руб",
        ]

        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "\n".join(lines))
        self.result_text.config(state=tk.DISABLED)

        self._last_result = dict(result)
        self._last_result["inputs"] = inputs
        self.btn_save_history.config(state=tk.NORMAL)

    def _save_to_history(self):
        if not self._last_result:
            return
        win = tk.Toplevel(self.root)
        win.title("Сохранить в историю")
        win.geometry("380x140")
        win.transient(self.root)
        win.configure(bg=BG_MAIN)
        f = ttk.Frame(win, padding=20)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="Период (например: Ноябрь 2025):").pack(anchor=tk.W)
        e_period = ttk.Entry(f, width=30)
        e_period.pack(fill=tk.X, pady=(0, 12))
        e_period.insert(0, default_period_name())
        e_period.focus()

        def do_save():
            period = (e_period.get() or "").strip()
            if not period:
                messagebox.showwarning("История", "Введите название периода.")
                return
            records = load_history()
            inp = self._last_result.get("inputs") or {}
            records.append({
                "period": period,
                "date_saved": datetime.now().strftime("%Y-%m-%d"),
                "sum_water": self._last_result["sum_water"],
                "sum_electricity": self._last_result["sum_electricity"],
                "total": self._last_result["total"],
                "xvs_curr": inp.get("xvs_curr"),
                "gvs_curr": inp.get("gvs_curr"),
                "el_day_curr": inp.get("el_day_curr"),
                "el_night_curr": inp.get("el_night_curr"),
            })
            if save_history(records):
                messagebox.showinfo("История", f"Период «{period}» сохранён в историю.")
                self._refresh_timeline()
                win.destroy()
            else:
                messagebox.showwarning("История", "Не удалось сохранить history.json.")

        ttk.Button(f, text="Сохранить", command=do_save).pack(anchor=tk.W)
        win.bind("<Return>", lambda e: do_save())

    def _show_history(self):
        records = load_history()
        win = tk.Toplevel(self.root)
        win.title("История по месяцам")
        win.geometry("580x400")
        win.transient(self.root)
        win.configure(bg=BG_MAIN)
        f = ttk.Frame(win, padding=20)
        f.pack(fill=tk.BOTH, expand=True)

        cols = ("period", "water", "electricity", "total", "date")
        tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        tree.heading("period", text="Период")
        tree.heading("water", text="Вода, руб")
        tree.heading("electricity", text="Свет, руб")
        tree.heading("total", text="Итого, руб")
        tree.heading("date", text="Дата сохранения")
        tree.column("period", width=140)
        tree.column("water", width=90)
        tree.column("electricity", width=90)
        tree.column("total", width=90)
        tree.column("date", width=110)
        scroll = ttk.Scrollbar(f, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Сортируем по дате (новые сверху)
        sorted_records = sorted(records, key=lambda r: r.get("date_saved", ""), reverse=True)
        total_sum = 0
        for r in sorted_records:
            total_sum += r.get("total", 0)
            tree.insert("", tk.END, values=(
                r.get("period", ""),
                f"{r.get('sum_water', 0):.2f}",
                f"{r.get('sum_electricity', 0):.2f}",
                f"{r.get('total', 0):.2f}",
                r.get("date_saved", ""),
            ))
        n = len(records)
        avg = total_sum / n if n else 0
        last3 = sum(r.get("total", 0) for r in sorted_records[:3])
        lines = [f"Всего за {n} мес.: {total_sum:,.2f} руб  |  В среднем: {avg:,.2f} руб/мес.".replace(",", " ")]
        if n >= 3:
            lines.append(f"  За последние 3 мес.: {last3:,.2f} руб".replace(",", " "))
        lbl = ttk.Label(f, text="  ".join(lines))
        lbl.pack(anchor=tk.W, pady=(8, 0))

    def _edit_tariffs(self):
        win = tk.Toplevel(self.root)
        win.title("Тарифы")
        win.geometry("400x340")
        win.transient(self.root)
        win.configure(bg=BG_MAIN)
        f = ttk.Frame(win, padding=20)
        f.pack(fill=tk.BOTH, expand=True)

        entries_t = {}
        rows = [
            ("Водоотведение, руб/м³", "tariff_sewage"),
            ("ХВС, руб/м³", "tariff_xvs"),
            ("ГВС, руб/м³", "tariff_gvs"),
            ("Подогрев, руб/Гкал", "tariff_heating_per_gcal"),
            ("Норматив Гкал/м³", "norm_gcal_per_m3"),
            ("Электричество день, руб/кВт·ч", "tariff_el_day"),
            ("Электричество ночь, руб/кВт·ч", "tariff_el_night"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            e = ttk.Entry(f, width=14)
            e.insert(0, str(self.config.get(key, DEFAULT_TARIFFS[key])))
            e.grid(row=i, column=1, padx=6, pady=2)
            entries_t[key] = e

        def save():
            new_config = {}
            for key in DEFAULT_TARIFFS:
                v = parse_float(entries_t[key].get(), DEFAULT_TARIFFS[key])
                if v is None or v < 0:
                    messagebox.showwarning("Тарифы", f"Некорректное значение для «{key}».")
                    return
                new_config[key] = v
            self.config = new_config
            if save_config(new_config):
                messagebox.showinfo("Тарифы", "Тарифы сохранены в config.json рядом с программой.")
            else:
                messagebox.showwarning("Тарифы", "Не удалось сохранить config.json.")
            win.destroy()

        ttk.Button(f, text="Сохранить", command=save).grid(
            row=len(rows), column=0, columnspan=2, pady=12
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
