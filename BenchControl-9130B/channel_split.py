"""Grid-based channel/graph layout; the graph never overlaps channel content."""
import tkinter as tk


def channel_height(requested, minimum, available, graph_minimum=200, divider=6):
    floor=max(1,minimum)
    return max(floor,min(requested,max(floor,available-graph_minimum-divider)))


class ChannelGraphSplit(tk.Frame):
    def __init__(self,parent):
        super().__init__(parent,bg='#0b1726',bd=0)
        self.top=None;self.bottom=None;self.top_min=1;self.bottom_min=200
        self.desired=1;self.visible=False;self.drag_y=None
        self.columnconfigure(0,weight=1)
        self.divider=tk.Frame(self,height=6,bg='#53677d',cursor='sb_v_double_arrow')
        self.preview=tk.Frame(self,height=6,bg='#a8b7c9')
        self.divider.bind('<ButtonPress-1>',self.begin_drag)
        self.divider.bind('<B1-Motion>',self.drag)
        self.divider.bind('<ButtonRelease-1>',self.end_drag)
        self.bind('<Configure>',lambda e:self.layout())

    def add(self,widget,minsize,stretch='always'):
        if self.top is None:
            self.top=widget;self.top_min=minsize;self.desired=minsize
            widget.grid(row=0,column=0,sticky='nsew')
        else:
            self.bottom=widget;self.bottom_min=minsize;self.visible=True
            widget.grid(row=2,column=0,sticky='nsew')
            self.divider.grid(row=1,column=0,sticky='ew')
        self.layout()

    def forget(self,widget):
        widget.grid_remove();self.divider.grid_remove();self.preview.place_forget()
        self.visible=False;self.drag_y=None;self.layout()

    def paneconfigure(self,widget,minsize):
        if widget is self.top:self.top_min=minsize
        else:self.bottom_min=minsize
        self.layout()

    def bounded(self,y):
        floor=max(self.top_min,self.top.winfo_reqheight())
        return channel_height(y,floor,self.winfo_height(),self.bottom_min)

    def layout(self):
        if self.top is None:return
        floor=max(self.top_min,self.top.winfo_reqheight())
        height=self.bounded(self.desired) if self.visible else floor
        self.rowconfigure(0,minsize=height,weight=0 if self.visible else 1)
        self.rowconfigure(1,minsize=6 if self.visible else 0,weight=0)
        self.rowconfigure(2,minsize=self.bottom_min if self.visible else 0,weight=1 if self.visible else 0)

    def sash_place(self,index,x,y):
        self.desired=self.bounded(y);self.layout()

    def sash_coord(self,index):return (0,self.top.winfo_height())

    def begin_drag(self,event):
        self.drag_y=self.top.winfo_height();self.drag(event)

    def drag(self,event):
        if not self.visible:return
        self.drag_y=self.bounded(event.y_root-self.winfo_rooty())
        self.preview.place(x=0,y=self.drag_y,relwidth=1,height=6)
        self.preview.lift()

    def end_drag(self,event):
        self.preview.place_forget()
        if self.drag_y is not None:self.sash_place(0,0,self.drag_y)
        self.drag_y=None
