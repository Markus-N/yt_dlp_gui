from tkinter import *


class Tooltip:
    """
    Create a tooltip for a given widget.
    Inpired by: https://stackoverflow.com/questions/3221956/how-do-i-display-tooltips-in-tkinter
    with some slight additions.
    Parameters:
    * widget: the widget to create a tooltip for
    * text: the initial text content (can be changed later)
    * offset: the position relative to the widget
    """
    def __init__(self, widget: Widget, text=None, offset: tuple[int, int] | None = None):
        self.widget: Widget = widget
        self.text: str | None = text
        self.wait_time: int = 500  # miliseconds
        self.wrap_length: int = 180  # pixels
        self.sustain_time: int = 1500  # miliseconds
        self.id = None
        self.tw = None
        self.offset: tuple = (5, -15) if offset is None else offset

        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def set_text(self, text: str = None):
        if text is None:
            self.unschedule()
            self.hide_tooltip()
        self.text = text

    def set_offset(self, offset: tuple):
        if offset is not None:
            self.offset = offset

    def enter(self, event = None):
        if self.text is not None:
            self.schedule()

    def leave(self, event = None):
        self.unschedule()
        self.hide_tooltip()
        # print('leave()')

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.wait_time, self.show_toolip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def show_toolip(self, event = None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + self.offset[0]
        y += self.widget.winfo_rooty() + self.offset[1]
        # creates a toplevel window
        self.tw = Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(self.tw, text=self.text, justify='left',
                      font='Arial 11 bold',
                      background="#ffffff", relief='solid', borderwidth=1,
                      wraplength=self.wrap_length)
        label.pack(ipadx=1)

    def hide_tooltip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

