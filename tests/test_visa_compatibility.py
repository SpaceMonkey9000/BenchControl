"""Exercise complete entry points with a VISA manager having no __enter__/__exit__."""
import json
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import benchmark
from instrument import DemoDevice
from app import Worker

class CompatibilityTests(unittest.TestCase):
    def run_benchmark(self, failed=False):
        device=DemoDevice();device.resource_name='USB0::TEST::INSTR';device.close=Mock()
        if failed:device.query=Mock(side_effect=TimeoutError('simulated timeout'))
        manager=SimpleNamespace(open_resource=Mock(return_value=device),close=Mock())
        module=SimpleNamespace(ResourceManager=Mock(return_value=manager))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(sys.modules,{'pyvisa':module}),patch.object(benchmark,'__file__',str(Path(tmp)/'benchmark.py')),patch.object(sys,'argv',['benchmark.py','--resource','USB0::TEST::INSTR','--count','1']),patch('builtins.print'):
                benchmark.main()
            report=json.loads(next(Path(tmp).glob('benchmark-*.json')).read_text())
        device.close.assert_called_once();manager.close.assert_called_once()
        return report
    def test_full_benchmark_with_legacy_manager(self):
        report=self.run_benchmark()
        self.assertEqual(report['status'],'completed');self.assertEqual(len(report['phases']),3)
    def test_failed_benchmark_closes_legacy_resources(self):
        report=self.run_benchmark(True)
        self.assertEqual(report['status'],'failed');self.assertIn('timeout',report['error'])
    def test_discovery_works_without_manager_context_protocol(self):
        manager=SimpleNamespace(list_resources=Mock(return_value=('PSU_ALIAS','USB0::TEST::INSTR')),close=Mock())
        module=SimpleNamespace(ResourceManager=Mock(return_value=manager))
        events=queue.Queue();worker=Worker(events)
        with patch.dict(sys.modules,{'pyvisa':module}):
            worker.post('scan')
            kind,resources=events.get(timeout=2)
        self.assertEqual(kind,'resources');self.assertEqual(resources,['PSU_ALIAS','USB0::TEST::INSTR'])
        manager.close.assert_called_once()

if __name__=='__main__':unittest.main()
