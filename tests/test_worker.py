import queue
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Worker

class WorkerTests(unittest.TestCase):
    def event(self,kind):
        for index,(name,data) in enumerate(self.pending):
            if name==kind:
                self.pending.pop(index)
                return data
        end=time.monotonic()+3
        while time.monotonic()<end:
            name,data=self.events.get(timeout=3)
            if name=='error':self.fail(str(data))
            if name==kind:return data
            self.pending.append((name,data))
        self.fail('Timed out waiting for '+kind)
    def setUp(self):
        self.pending=[]
        self.events=queue.Queue();self.worker=Worker(self.events)
        self.worker.post('connect','',True)
        self.event('connected');self.event('snapshot')
    def tearDown(self):
        self.worker.post('disconnect');self.event('disconnected')
    def test_demo_control_round_trip(self):
        self.worker.post('apply',3,2.5,.2)
        self.event('done');rows=self.event('snapshot')
        self.assertEqual(rows[2].set_voltage,2.5)
        self.assertFalse(rows[2].enabled)
        self.worker.post('output',3,True,(2.5,.2))
        self.event('done');self.assertTrue(self.event('snapshot')[2].enabled)
        self.worker.post('all_off');self.event('done')
        self.assertFalse(any(r.enabled for r in self.event('snapshot')))
    def test_refresh_rate_and_demo_cc(self):
        self.worker.post('output',1,True,(3.3,.1))
        self.event('done');self.event('snapshot')
        self.worker.post('demo_cc',1,True)
        self.assertTrue(self.event('snapshot')[0].current_limited)
        self.worker.post('rate',5)
        self.event('snapshot')
        started=time.monotonic()
        for _ in range(4):self.event('snapshot')
        elapsed=time.monotonic()-started
        self.assertLess(elapsed,1.5)
        self.assertGreater(elapsed,.5)
    def test_pending_enable_cancelled_by_alloff(self):
        # Hold submission lock until both queue items are inserted.
        # Worker may dequeue enable, but generation check must cancel it.
        with self.worker.lock:
            self.worker.generation+=1
            generation=self.worker.generation
            self.worker.jobs.put((10,next(self.worker.serial),generation-1,'output',(1,True,(3.3,.1))))
            self.worker.jobs.put((0,next(self.worker.serial),generation,'all_off',()))
        self.event('done')
        self.assertFalse(any(r.enabled for r in self.event('snapshot')))
        self.assertEqual(self.event('cancelled'),'output')

if __name__=='__main__':unittest.main()
