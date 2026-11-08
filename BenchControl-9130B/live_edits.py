"""Debounced user edits. No automatic writes from snapshots or mode changes."""
class LiveEdits:
    def __init__(self,scheduler,send):
        self.scheduler=scheduler;self.send=send;self.pending={}

    def queue(self,channel,field,delay=750):
        key=(channel,field)
        self.cancel_key(key)
        self.pending[key]=self.scheduler.after(delay,lambda:self.flush(key))

    def flush(self,key):
        if key not in self.pending:return
        self.pending.pop(key)
        self.send(*key)

    def cancel_key(self,key):
        job=self.pending.pop(key,None)
        if job is not None:self.scheduler.after_cancel(job)

    def cancel(self):
        for key in list(self.pending):self.cancel_key(key)
