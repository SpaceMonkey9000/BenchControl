"""Explicit three-way disconnect/close choice."""
import tkinter as tk
from tkinter import ttk


class DisconnectDialog(tk.Toplevel):
    def __init__(self,parent,closing=False):
        super().__init__(parent);self.result=None
        self.title('Close BenchControl' if closing else 'Disconnect')
        self.transient(parent);self.resizable(False,False)
        self.protocol('WM_DELETE_WINDOW',self.cancel)
        body=ttk.Frame(self,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Choose what happens to the PSU outputs.',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,16))
        action='close' if closing else 'disconnect'
        ttk.Button(body,text='Leave outputs at current state',command=lambda:self.choose('leave')).pack(fill='x',pady=4)
        ttk.Button(body,text=f'Switch off all outputs and {action}',command=lambda:self.choose('off')).pack(fill='x',pady=4)
        cancel=ttk.Button(body,text='Cancel',command=self.cancel);cancel.pack(fill='x',pady=4)
        self.bind('<Escape>',lambda e:self.cancel())
        self.update_idletasks()
        x=parent.winfo_rootx()+max(0,(parent.winfo_width()-self.winfo_reqwidth())//2)
        y=parent.winfo_rooty()+max(0,(parent.winfo_height()-self.winfo_reqheight())//2)
        self.geometry(f'+{x}+{y}')
        self.grab_set();cancel.focus_set()
    def choose(self,result):self.result=result;self.destroy()
    def cancel(self):self.choose(None)


def ask_disconnect(parent,closing=False):
    dialog=DisconnectDialog(parent,closing)
    parent.wait_window(dialog)
    return dialog.result
