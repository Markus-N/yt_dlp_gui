#!/usr/bin/python

import glob
import json
import os
import random
import re
import sys
import threading
import time
from argparse import ArgumentParser, Namespace
from threading import Thread
from tkinter import (Frame, Toplevel, Label, Button, Entry, Text, ttk, StringVar, Widget, PhotoImage, filedialog, END)
from typing import Any

import yt_dlp as yt
from tkinterdnd2 import TkinterDnD, DND_TEXT

from tooltip import Tooltip


MAIN_WINDOW_TITLE = 'yt-dl GUI'
SORT_DIALOG_TITLE = 'Sort Download directories'
SORT_HELP_TEXT = 'Use this like a text editor, but don\'t break lines.'
TABLE_HEADERS: [str] = ['St.', 'URL / Title', 'Video Format', 'Target Dir']
DOWNLOAD_STATUS_PREFIX: str = 'Download-Status: '

DL_STATUS_WAITING: str = 'Waiting'
DL_STATUS_RUNNING: str = 'Running'
DL_STATUS_DONE: str = 'Done'
DL_STATUS_ERROR: str = 'Error'

ALL_DL_STATUS_VALUES: [str] = [DL_STATUS_WAITING, DL_STATUS_RUNNING, DL_STATUS_DONE, DL_STATUS_ERROR]

SYMBOL_HOURGLASS_NOT_DONE: str = '\u23f3'
SYMBOL_PLAY: str = '\u25b6'
SYMBOL_COLLISION: str = '\U0001f4a5'
SYMBOL_RACING_FINISH_FLAG: str = '\U0001f3c1'

SYMBOL_PLUS: str = '\u002b'
SYMBOL_HEAVY_PLUS: str = '\u2795'
SYMBOL_HEAVY_MINUS: str = '\u2796'
SYMBOL_ARROWS_UP_DOWN: str = '\u21c5'
SYMBOL_DOWN_ARROW: str = '\u21e9'
SYMBOL_DOWN_ARROW_BAR: str = '\u2913'
SYMBOL_TRASH: str = '\ue020'
SYMBOL_BROOM: str = '\U0001f9f9'
SYMBOL_RECYCLING: str = '\u267b'
SYMBOL_WASTEBASKET: str = '\U0001f5d1'
SYMBOL_GEAR: str = '\u2699'
SYMBOL_FLOPPY: str = '\U0001f4Be'
SYMBOL_OK: str = '\u2714'
SYMBOL_CANCEL: str = '\U0001f5d9'

STATUS_ICON_MAP: {} = {
    DL_STATUS_WAITING: SYMBOL_HOURGLASS_NOT_DONE,
    DL_STATUS_RUNNING: SYMBOL_PLAY,
    DL_STATUS_DONE: SYMBOL_RACING_FINISH_FLAG,
    DL_STATUS_ERROR: SYMBOL_COLLISION
}

STATUS_TOOLTIP_MAP: {} = {
    DL_STATUS_WAITING: 'Waiting',
    DL_STATUS_RUNNING: 'Running',
    DL_STATUS_DONE: 'Done',
    DL_STATUS_ERROR: 'Error'
}

YOUTUBE_PREFIX: str = 'https://www.youtube.com/'

RE_VIDEO_TITLE: re.Pattern[str] = re.compile('[0-9]{8} (.*) {2}[0-9]*x[0-9]* ')

COLOR_FATAL: str = '\033[1;37;41m'
COLOR_RESET: str = '\033[0m'

STDOUT = sys.stdout


def delimiter(title: str | None = None):
    columns: int
    try:
        terminal_size = os.get_terminal_size(0)
        columns = terminal_size.columns
    except Exception as e:
        columns = 80
    prefix = '─── ' + title + ' ' if title is not None else ''
    prefix_len: int = len(prefix)
    print(prefix + ((columns - 1 - prefix_len) * '─'), file=STDOUT, flush=True)


def select_all(widget):
    widget.select_range(0, END)
    return 'break'


class Download:
    def __init__(self, url: str, target_dir: str, video_format: str):
        self.url: str = url
        self.video_id: str = re.sub(r'.*[/=]', '', url)
        self.title: str | None = None
        self.target_dir: str = target_dir
        self.video_format: str = video_format
        self.status: str = DL_STATUS_WAITING


class DownloadTable:
    def __init__(self, parent, reset_handler, headers: [str]):
        self.reset_handler = reset_handler
        self.parent = parent
        self.total_columns = len(headers)
        self.rows: [[Widget]] = []
        self.col_num_status: int = 0
        self.col_num_url: int = 1
        col_num: int = 0
        header_entries: [Widget] = []
        for header in headers:
            header_label: Label = Label(self.parent, text=header)
            header_label.grid(row=0, column=col_num, sticky='w', padx=(0, 0), pady=(0, 0))
            header_entries.append(header_label)
            col_num += 1
        self.rows.append(header_entries)

    def add_row(self, dl: Download):
        row_num: int = len(self.rows)
        # print('add_row("' + dl.url + '") => row ', row_num)

        column_0: Entry = Entry(self.parent, width=2, disabledbackground="white", disabledforeground="black")
        column_0.grid(row=row_num, column=0, sticky='w', padx=(0, 0), pady=(0, 0))
        column_0.insert(END, STATUS_ICON_MAP[dl.status])
        column_0.configure(state='disabled')
        column_0.tooltip = Tooltip(column_0, STATUS_TOOLTIP_MAP[dl.status], (5, 15))
        column_0.bind('<Double-Button-1>', lambda v: self.reset_row(dl.url))

        column_1: Entry = Entry(self.parent, width=20, disabledbackground="white", disabledforeground="black")
        column_1.grid(row=row_num, column=1, sticky='w', padx=(0, 0), pady=(0, 0))
        column_1.insert(END, dl.url)
        column_1.configure(state='disabled')
        tooltip_text: str = dl.video_id if dl.title is None or dl.title == '' else dl.title
        column_1.tooltip = Tooltip(column_1, tooltip_text, (5, 15))

        column_2: Entry = Entry(self.parent, width=8, disabledbackground="white", disabledforeground="black")
        column_2.grid(row=row_num, column=2, sticky='w', padx=(0, 0), pady=(0, 0))
        column_2.insert(END, dl.video_format)
        column_2.configure(state='disabled')

        column_3: Entry = Entry(self.parent, disabledbackground="white", disabledforeground="black")
        column_3.grid(row=row_num, column=3, sticky='ew', padx=(0, 0), pady=(0, 0))
        column_3.insert(END, dl.target_dir)
        column_3.configure(state='disabled')

        self.parent.columnconfigure(3, weight=1)
        row_items: [Widget] = [column_0, column_1, column_2, column_3]
        self.rows.append(row_items)

    def update_row(self, dl: Download, error_msg: str = None):
        row_num: int = self.find_row(download=dl)
        if row_num is not None:
            # update status tooltip
            status_entry: Entry = self.parent.grid_slaves(row=row_num, column=0)[0]
            status_entry.configure(state='normal')
            status_entry.delete(0, END)
            status_entry.insert(END, STATUS_ICON_MAP[dl.status])
            status_entry.configure(state='disabled')
            status_tooltip_text = STATUS_TOOLTIP_MAP[dl.status] if error_msg is None else error_msg
            status_entry.tooltip.text = status_tooltip_text
            # update title tooltip
            title_tooltip_text: str = dl.video_id if (dl.title is None or dl.title == '') else dl.title
            url_entry: Entry = self.parent.grid_slaves(row=row_num, column=1)[0]
            url_entry.tooltip.text = title_tooltip_text

    def remove_row(self, dl: Download):
        row_num: int = self.find_row(download=dl)
        if row_num is not None:
            widgets_to_delete = self.rows[row_num]
            widgets_to_delete.reverse()
            for widget in widgets_to_delete:
                widget.grid_forget()
                widget.destroy()
            self.rows.pop(row_num)
            while row_num < len(self.rows):
                widgets_to_move_up = self.rows[row_num]
                for widget_to_move_up in widgets_to_move_up:
                    widget_to_move_up.grid(row=row_num)
                row_num += 1

    def reset_row(self, url: str):
        self.reset_handler.reset_download(url)

    def find_row(self, download: Download) -> int | None:
        row_num: int = 0
        while row_num < len(self.rows):
            row_num += 1
            grid_slaves = self.parent.grid_slaves(row=row_num, column=1)
            if grid_slaves:
                url_entry: Entry = grid_slaves[0]
                url: str = url_entry.get()
                if url == download.url:
                    return row_num
        return None


class YtDlGUI:
    def __init__(self, parent):
        self.parent = parent
        self.settings = self._read_config()
        self.download_archive_filename = self.settings['download_archive']
        self.window_icon: PhotoImage | None = None

        icon_filename: str = self.settings['icon']
        if icon_filename is not None:
            # icon filename can be absolute (i.e. start with e.g. a '/',
            # or relative to the location of the program itself
            if not icon_filename.startswith(os.sep):
                icon_filename = str(os.path.dirname(__file__)) + os.sep + icon_filename
            self.window_icon = PhotoImage(file=icon_filename)
            root.iconphoto(False, self.window_icon)

        self.video_formats: [] = self.settings['video_formats']
        self.target_dirs: [] = self.settings['target_dirs']
        self.temp_dir = self.settings['temp_dir']
        self.active_download: Download | None = None

        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.download_queue: [Download] = []

        self.do_stop: bool = False
        self.preselected_format: str | None = None
        self.buttons = []
        self._init_ui()

        # ensure that "postprocessing" is there and has all entries, so we don't need to check during runtime
        if 'postprocessing' not in self.settings:
            self.settings['postprocessing'] = {}
        postprocessing_settings = self.settings['postprocessing']
        if 'underscores_to_spaces' not in postprocessing_settings:
            postprocessing_settings['underscores_to_spaces'] = False
        if 'remove_at_sign' not in postprocessing_settings:
            postprocessing_settings['remove_at_sign'] = False
        if 'add_newlines_to_description' not in postprocessing_settings:
            postprocessing_settings['add_newlines_to_description'] = False
        if 'delete_empty_description' not in postprocessing_settings:
            postprocessing_settings['delete_empty_description'] = False
        if 'rename_description' not in postprocessing_settings:
            postprocessing_settings['rename_description'] = False
        if 'rename_description_suffix' not in postprocessing_settings:
            postprocessing_settings['rename_description_suffix'] = '.txt'
        if 'add_tumb' not in postprocessing_settings:
            postprocessing_settings['add_tumb'] = False
        if 'subtitles_dots_to_underscores' not in postprocessing_settings:
            postprocessing_settings['subtitles_dots_to_underscores'] = False

    def _read_config(self):
        self.config_file = os.path.dirname(__file__) + os.sep + 'yt_dl_gui.json'
        with open(self.config_file, 'r') as in_file:
            settings = json.load(in_file)
        return settings

    def _init_ui(self):
        self.parent.title(MAIN_WINDOW_TITLE)

        # Define the style for combobox widget
        style = ttk.Style()
        style.map('TCombobox', fieldbackground=[('readonly', 'white')])
        style.map('TCombobox', selectbackground=[('readonly', 'white')])
        style.map('TCombobox', selectforeground=[('readonly', 'black')])

        row_num: int = 0

        self.label_url = Label(master=self.parent, text="URL")
        self.label_url.grid(row=row_num, column=0, sticky='w', padx=(6, 6))
        self.url_var: StringVar = StringVar()
        self.url_var.trace_add(mode='write', callback=self.url_changed)
        self.entry_url = Entry(master=self.parent, textvariable=self.url_var, width=80)
        self.entry_url.grid(row=row_num, column=1, columnspan=3, sticky='ew', padx=(6, 6))

        self.entry_url.drop_target_register(DND_TEXT)
        self.entry_url.dnd_bind('<<Drop>>', lambda e: self.drop_url(e.data))
        self.entry_url.bind("<Control-a>", lambda e: select_all(e.widget))

        row_num += 1

        self.label_target_dir = Label(master=self.parent, text="T-Dir")
        self.label_target_dir.grid(row=row_num, column=0, sticky='w', padx=(6, 6))
        self.entry_target_dir = ttk.Combobox(master=self.parent,
                                             state='readonly',
                                             values=self.target_dirs)
        self.entry_target_dir.grid(row=row_num, column=1, sticky='nsew', padx=(6, 6))
        self.entry_target_dir.bind("<<ComboboxSelected>>", self.dir_selection_changed)
        self.entry_target_dir.current(0)

        dir_buttons_frame = Frame(master=self.parent)
        self.add_dir_button = Button(master=dir_buttons_frame,
                                     text=SYMBOL_HEAVY_PLUS,
                                     font='Arial 10 bold',
                                     foreground='green',
                                     padx=3,
                                     pady=1,
                                     command=self.add_download_dir)
        self.add_dir_button.tooltip = Tooltip(self.add_dir_button, 'Add download directory', (15, 15))
        self.add_dir_button.pack(side='left')
        self.remove_dir_button = Button(master=dir_buttons_frame,
                                        text=SYMBOL_HEAVY_MINUS,
                                        font='Arial 10 bold',
                                        foreground='red',
                                        padx=3,
                                        pady=1,
                                        command=self.remove_download_dir)
        self.remove_dir_button.tooltip = Tooltip(self.remove_dir_button, 'Remove selected download directory', (15, 15))
        self.remove_dir_button.pack(side='left')
        self.sort_dirs_button = Button(master=dir_buttons_frame,
                                       text=SYMBOL_ARROWS_UP_DOWN,
                                       font='Arial 10 bold',
                                       padx=3,
                                       pady=1,
                                       command=self.sort_download_dirs)
        self.sort_dirs_button.tooltip = Tooltip(self.sort_dirs_button, 'Reorder download directories', (15, 15))
        self.sort_dirs_button.pack(side='left')
        self.save_dirs_button = Button(master=dir_buttons_frame,
                                       text=SYMBOL_FLOPPY,
                                       font='Arial 10 bold',
                                       padx=3,
                                       pady=1,
                                       command=self.save_config)
        self.save_dirs_button.tooltip = Tooltip(self.save_dirs_button, 'Save download directories', (15, 15))
        self.save_dirs_button.pack(side='left')

        dir_buttons_frame.grid(row=row_num, column=2, padx=(0, 6))
        self.parent.columnconfigure(1, weight=1)

        row_num += 1

        dl_buttons_frame = Frame(master=self.parent)

        cleanup_button = Button(master=dl_buttons_frame,
                                text=SYMBOL_WASTEBASKET,
                                command=self.cleanup_queue)
        cleanup_button.tooltip = Tooltip(cleanup_button, 'Remove finished downloads from table', (15, 15))
        cleanup_button.pack(side='left')

        add_icon_label = Label(master=dl_buttons_frame,
                               text=SYMBOL_DOWN_ARROW,
                               font='Arial 18 bold',
                               foreground='green')
        add_icon_label.pack(side='left', padx=(40, 2))

        for format in self.video_formats:
            format_text = format[0]
            format_button = Button(master=dl_buttons_frame,
                                    text=format_text,
                                    relief='raised',
                                    command=lambda label=format_text: self.switch_format(label))
            format_button.pack(side='left')
            self.buttons.append(format_button)

        dl_buttons_frame.grid(row=row_num, column=0, columnspan=3, padx=(6, 6))

        row_num += 1

        self.table_frame: Frame = Frame(master=self.parent)
        self.table_frame.grid(row=row_num, column=0, columnspan=3, sticky='ew', padx=(6, 6))
        self.download_table: DownloadTable = DownloadTable(self.table_frame, self, TABLE_HEADERS)

        self.downloader_event: threading.Event = threading.Event()
        self.downloader_event.clear()
        self.processor = Thread(target=self.process_queue, daemon=True)
        if commandline_args.ui_test:
            i: int = 0
            while i < 9:
                i += 1
                dl: Download = Download('watch?v=' + 11 * str(i), 'Title ' + str(i), self.target_dirs[0], 'NO LIMIT')
                dl.status = ALL_DL_STATUS_VALUES[i % len(ALL_DL_STATUS_VALUES)]
                self.download_queue.append(dl)
                self.download_table.add_row(dl)

        row_num += 1

        self.status_frame: Frame = Frame(master=self.parent)
        self.status_frame.grid(row=row_num, column=0, columnspan=4, sticky='ew', padx=(0, 0), pady=(6, 0))
        self.status_label = Label(master=self.status_frame, anchor='w', relief='sunken', text=DOWNLOAD_STATUS_PREFIX)
        self.status_label.pack(fill='x', padx=(0, 0), pady=(0, 0))

        if not commandline_args.no_download and not commandline_args.ui_test:
            self.processor.start()

        self.entry_url.focus()

    def drop_url(self, data):
        self.entry_url.delete(0, END)
        return self.entry_url.insert(END, data)

    def reset_download(self, url: str):
        queue_element: Download
        for queue_element in self.download_queue:
            if queue_element.url == url:
                if queue_element.status == DL_STATUS_ERROR:
                    queue_element.status = DL_STATUS_WAITING
                    self.download_table.update_row(queue_element)
                    file_names: list = glob.glob(queue_element.target_dir + os.sep + '*' + queue_element.video_id + '*')
                    if len(file_names) > 0:
                        for file_name in file_names:
                            os.remove(file_name)
                self.downloader_event.set()
                break

    def cleanup_queue(self):
        dl: Download
        download_queue_remaining: [Download] = []
        self.download_queue.reverse()
        for dl in self.download_queue:
            if dl.status == DL_STATUS_DONE:
                self.download_table.remove_row(dl)
            else:
                download_queue_remaining.append(dl)
        download_queue_remaining.reverse()
        self.download_queue.clear()
        self.download_queue.extend(download_queue_remaining)

    def on_closing(self):
        print('Main window closed.')
        self.do_stop = True

    def cleanup_url(self):
        url: str = self.entry_url.get()
        if not url:
            return
        # remove additional parameters from URL
        url = re.sub(r'&.*', '', url)
        # also clear from entry
        self.entry_url.delete(len(url), END)

    def can_download(self, video_format: str = None) -> bool:
        url: str = self.entry_url.get()
        if not url:
            return False
        if YOUTUBE_PREFIX not in url or url.index(YOUTUBE_PREFIX) != 0:
            return False
        dir_selection: str = self.entry_target_dir.get()
        if dir_selection not in self.target_dirs:
            return False

        # check if video_format is in catalog
        if video_format is not None:
            matching_video_formats: [[str, str]] = [entry for entry in self.video_formats if entry[0] == video_format]
            if len(matching_video_formats) != 1:
                return False

        video_id: str = url[-11:]

        # check if video_id is already in queue
        queue_element: Download
        for queue_element in self.download_queue:
            if video_id in queue_element.url:
                return False

        if os.path.exists(dir_selection) and os.path.isdir(dir_selection):
            # check for existing files
            files: list = glob.glob(dir_selection + os.sep + '*' + video_id + '*')
            if len(files) > 0:
                return False

            # check for entry in archive file
            archive_file = dir_selection + os.sep + self.download_archive_filename
            if os.path.exists(archive_file):
                with open(archive_file) as in_file:
                    lines = in_file.read().splitlines()
                    in_file.close()
                if 'youtube ' + video_id in lines:
                    return False
        return True

    def url_changed(self, *args):
        self.cleanup_url()
        if self.preselected_format:
            if self.can_download(self.preselected_format):
                self.add_download_to_queue(self.preselected_format)
            else:
                self.entry_url.delete(0, END)

    def dir_selection_changed(self, event):
        self.entry_target_dir.selection_range(0, 0)

    def switch_format(self, video_format: str):
        url = self.entry_url.get()
        if url:
            self.preselected_format = None
            for button in self.buttons:
                if button['text'] == video_format:
                    button.configure(relief='sunken')
            self.add_download_to_queue(video_format)
            for button in self.buttons:
                button.configure(relief='raised')
        else:
            for button in self.buttons:
                relief: str = 'raised'
                if button['text'] == video_format:
                    if self.preselected_format == video_format:
                        self.preselected_format = None
                    else:
                        self.preselected_format = video_format
                        relief = 'sunken'
                button.configure(relief=relief)

    def add_download_to_queue(self, video_format: str):
        url = self.entry_url.get()
        if url is not None and url.index(YOUTUBE_PREFIX) == 0:
            url = url[len(YOUTUBE_PREFIX):]
            target_dir = self.entry_target_dir.get()
            dl: Download = Download(url, target_dir, video_format)
            self.entry_url.delete(0, END)
            self.entry_url.focus()
            self.download_queue.append(dl)
            self.download_table.add_row(dl)
            self.downloader_event.set()

    def add_download_dir(self):
        target_dir: str = self.entry_target_dir.get()
        directory: str = filedialog.askdirectory(initialdir=target_dir)
        cwd: str = os.getcwd()
        if directory.startswith(cwd):
            directory = directory[len(cwd) + 1:]
        if directory in self.target_dirs:
            return
        self.target_dirs.append(directory)
        self.entry_target_dir['values'] = self.target_dirs
        self.entry_target_dir.current(self.target_dirs.index(directory))

    def remove_download_dir(self):
        if len(self.target_dirs) < 2:
            # do not remove the last remaining dir
            return
        target_dir: str = self.entry_target_dir.get()
        self.target_dirs.remove(target_dir)
        self.entry_target_dir['values'] = self.target_dirs
        self.entry_target_dir.current(0)

    def sort_download_dirs(self):
        self.dialog_window: Toplevel = Toplevel(root)
        if self.window_icon is not None:
            self.dialog_window.iconphoto(False, self.window_icon)
        self.dialog_window.title(SORT_DIALOG_TITLE)

        label_frame: Frame = Frame(self.dialog_window)
        label: Label = Label(label_frame, text=SORT_HELP_TEXT)
        label.pack(side='left')
        label_frame.pack(fill='x', expand=True)
        self.edit_dirs_text: Text = Text(self.dialog_window, width=40, height=15)
        self.edit_dirs_text.insert(END, '\n'.join(self.target_dirs))
        self.edit_dirs_text.pack(fill='both', expand=True)
        self.edit_dirs_text.focus_set()
        buttons_frame: Frame = Frame(self.dialog_window)
        ok_button: Button = Button(master=buttons_frame,
                                   text=SYMBOL_OK,
                                   font='Arial 10 bold',
                                   foreground='green',
                                   padx=3,
                                   pady=1,
                                   command=self.sort_download_dirs_ok)
        cancel_button: Button = Button(master=buttons_frame,
                                       text=SYMBOL_CANCEL,
                                       font='Arial 10 bold',
                                       foreground='red',
                                       padx=3,
                                       pady=1,
                                       command=self.sort_download_dirs_cancel)
        cancel_button.pack(side='right')
        ok_button.pack(side='right')
        buttons_frame.pack(fill='x', expand=True)

    def sort_download_dirs_ok(self):
        edit_text: str = self.edit_dirs_text.get('1.0',END)
        target_dirs: [str] = edit_text.split('\n')
        self.target_dirs = [ target_dir for target_dir in target_dirs if target_dir != '' ]
        self.entry_target_dir['values'] = self.target_dirs
        self.entry_target_dir.current(0)
        self.dialog_window.destroy()

    def sort_download_dirs_cancel(self):
        self.dialog_window.destroy()

    def save_config(self):
        self.settings['target_dirs'] = self.target_dirs
        json_string = json.dumps(obj=self.settings, indent=4, sort_keys=False) + '\n'
        # we want to have a newline at the end of the file.
        with open(self.config_file, 'w') as out_file:
            out_file.write(json_string)

    def process_queue(self):
        print('Downloader thread started.')
        while not self.do_stop:
            # print('Waiting for processing queue to be released ...')
            self.downloader_event.wait()
            print('Processing queue.')
            count_waiting: int = 0
            queue_element: Download
            for queue_element in self.download_queue:
                if queue_element.status == DL_STATUS_WAITING:
                    queue_element.status = DL_STATUS_RUNNING
                    self.download_table.update_row(queue_element)
                    try:
                        self.active_download = queue_element
                        (rc, video_title) = self.do_download(YOUTUBE_PREFIX + queue_element.url,
                                                             queue_element.target_dir,
                                                             queue_element.video_format)
                        if rc == 0:
                            queue_element.status = DL_STATUS_DONE
                            if video_title is not None:
                                queue_element.title = video_title
                        else:
                            queue_element.status = DL_STATUS_ERROR
                        self.download_table.update_row(queue_element)
                    except Exception as e:
                        queue_element.status = DL_STATUS_ERROR
                        self.download_table.update_row(queue_element, repr(e))
                    finally:
                        self.active_download = None
                        self.status_label.configure(text=DOWNLOAD_STATUS_PREFIX)

                    count_waiting = len([dl for dl in self.download_queue if dl.status == DL_STATUS_WAITING])
                    if count_waiting > 0:
                        self.status_label.configure(text=DOWNLOAD_STATUS_PREFIX + 'wait a bit before next download ...')
                        sleep_time = random.uniform(1.5, 5.5)
                        time.sleep(sleep_time)
                        self.status_label.configure(text=DOWNLOAD_STATUS_PREFIX)
                    break
            if count_waiting == 0:
                self.downloader_event.clear()
                delimiter('Nothing to download, waiting ...')
        print('Downloader thread ended.')

    def progress_hook(self, response):
        # print('Progress hook called:', response['_default_template'])
        status_text = response['_default_template']
        status_text = re.sub(r'\x1b\[[0-9;]*m', '', status_text)  # remove coloring escape sequences
        self.status_label.configure(text=DOWNLOAD_STATUS_PREFIX + status_text)

    def do_download(self, url: str, target_dir: str, video_format: str) -> (int, str | None):
        video_id: str = url.replace('https://www.youtube.com/watch?v=', '')
        video_id: str = video_id.replace('https://www.youtube.com/shorts/', '')
        delimiter(video_id)
        cwd: str = os.getcwd() + os.sep

        print('Download ' + url + ' [' + video_format + '] => ' + target_dir + ' ...')
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        yt_dl_params: {} = self.settings['yt_dl_params'].copy()
        # keep the yt_dl_params from settings unchanged because they will be reused

        archive_file = target_dir + os.sep + self.download_archive_filename
        yt_dl_params['download_archive'] = archive_file
        yt_dl_params['paths'] = {
            "temp": cwd + self.temp_dir,
            "home": cwd + target_dir
        }
        selected_video_formats: [[str, str]] = [entry for entry in self.video_formats if entry[0] == video_format]
        video_format: str = selected_video_formats[0][1]
        # print('video_format:', video_format, 'video_format', video_format)
        yt_dl_params['format'] = video_format

        # with open('yt_dl_fe_debug_settings.json', 'w') as out_file:
        #     out_file.write(json.dumps(obj=self.settings, indent=4, sort_keys=False) + '\n')
        # with open('yt_dl_fe_debug_params.json', 'w') as out_file:
        #     out_file.write(json.dumps(obj=yt_dl_params, indent=4, sort_keys=False) + '\n')

        yt_dl = yt.YoutubeDL(params=yt_dl_params, auto_init=True)
        yt_dl.add_progress_hook(self.progress_hook)
        dl_rc: int = yt_dl.download(url)
        video_title: str | None = None
        if dl_rc == 0:
            video_title = self.do_post_processing(video_id, target_dir)
            print("Postprocessing done.")
        return dl_rc, video_title

    def do_post_processing(self, video_id, target_dir) -> str | None:
        print()
        print("Download done.")
        print('video_id = ' + video_id)
        video_title_old: str | None = None
        video_title_new: str | None = None
        file_names: list = glob.glob(target_dir + os.sep + '*' + video_id + '*')
        postprocessing_settings = self.settings['postprocessing']
        if len(file_names) > 0:
            re_list: list[Any] = RE_VIDEO_TITLE.findall(file_names[0])
            if len(re_list) > 0:
                for re_item in re_list:
                    video_title_old = re_item
                    video_title_new = video_title_old
                    if postprocessing_settings['underscores_to_spaces']:
                        video_title_new = video_title_new.replace('_', ' ')
                    if postprocessing_settings['remove_at_sign']:
                        video_title_new = re.sub(r'^@', '', video_title_new)
                    # print('video_title old = ' + video_title_old)
                    # print('video_title new = ' + video_title_new)
        for file_name in file_names:
            if video_id + '.description' in file_name:
                size = os.path.getsize(file_name)
                if size > 0:
                    if postprocessing_settings['add_newlines_to_description']:
                        # add 2 newlines
                        with open(file_name, 'a') as description_file:
                            description_file.write('\n\n')
                            description_file.close()
                elif postprocessing_settings['delete_empty_description']:
                    print('description is empty.')
                    os.remove(file_name)
                    continue
            if video_title_old is not None:
                file_name_new = file_name.replace(video_title_old, video_title_new)
                if postprocessing_settings['rename_description']:
                    file_name_new = file_name_new.replace('.description', postprocessing_settings['rename_description_suffix'])
                if postprocessing_settings['add_tumb']:
                    file_name_new = file_name_new.replace('.jpg', '_thumb.jpg')
                    file_name_new = file_name_new.replace('.png', '_thumb.png')
                    file_name_new = file_name_new.replace('.webp', '_thumb.webp')
                if postprocessing_settings['subtitles_dots_to_underscores']:
                    file_name_new = re.sub(r'\.(..)\.vtt', r'_\1.vtt', file_name_new)
                os.rename(file_name, file_name_new)
                # old debugging stuff
                # print()
                # print('video_title_old :', video_title_old)
                # print('video_title_new :', video_title_new)
                # print('file_name       :', file_name)
                # print('file_name_new   :', file_name_new)

        return video_title_new


parser: ArgumentParser = ArgumentParser(description='Simple GUI for yt-dlp')

parser.add_argument('-n', '--no-download', action='store_true', help='No actual download, e.g. for testing the button mechanics')
parser.add_argument('-u', '--ui-test', action='store_true', help='No actual download, plus dummy table entries for layout test')
parser.parse_args()

commandline_args: Namespace = parser.parse_args()

root = TkinterDnD.Tk()
dl_gui = YtDlGUI(root)

# root.protocol("WM_DELETE_WINDOW", dl_gui.on_closing())
root.mainloop()
