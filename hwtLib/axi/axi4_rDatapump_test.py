import unittest

from hdl_toolkit.hdlObjects.specialValues import Time
from hdl_toolkit.simulator.agentConnector import agInts
from hdl_toolkit.simulator.shortcuts import simUnitVcd, simPrepare
from hwtLib.axi.axi4_rDatapump import Axi4_RDataPump


class Axi4_rDatapumpTC(unittest.TestCase):
    def setUp(self):
        u = Axi4_RDataPump()
        self.u, self.model, self.procs = simPrepare(u)
    
    def doSim(self, name, time):
        simUnitVcd(self.model, self.procs,
                    "tmp/axi4_rDatapump_" + name + ".vcd",
                    time=time)
    
    def test_nop(self):
        u = self.u
        self.doSim("nop", 500 * Time.ns)
        
        self.assertEqual(len(u.ar._ag.data), 0)
        self.assertEqual(len(u.rOut._ag.data), 0)
        
    def test_notSplitedReq(self):
        u = self.u
        
        req = u.req._ag
        r = u.r._ag
        
        # download one word from addr 0xff
        req.data.append(req.mkReq(0xff, 0))
        self.doSim("notSplited", 500 * Time.ns)
        
        self.assertEqual(len(req.data), 0)
        self.assertEqual(len(u.ar._ag.data), 1)
        self.assertEqual(len(u.rOut._ag.data), 0)
        
        

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(Axi4_rDatapumpTC('test_notSplited'))
    #suite.addTest(unittest.makeSuite(Axi4_rDatapumpTC))
    runner = unittest.TextTestRunner(verbosity=3)
    runner.run(suite)