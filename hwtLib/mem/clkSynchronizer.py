from hdl_toolkit.intfLvl import connect, Unit
from hdl_toolkit.hdlObjects.types.defs import BIT
from hdl_toolkit.interfaces.std import Rst, Signal, Clk

c = connect

class ClkSynchronizer(Unit):
    """
    Signal synchronization between two clock domains
    http://www.sunburst-design.com/papers/CummingsSNUG2008Boston_CDC.pdf
    """
    
    def _config(self):
        self.DATA_TYP = BIT
        
    def _declr(self):
        with self._asExtern():
            self.rst = Rst()
            
            self.inData = Signal(dtype=self.DATA_TYP)
            self.inClk = Clk()
            
            self.outData = Signal(dtype=self.DATA_TYP)
            self.outClk = Clk()
        
        
    def _impl(self):
        def reg(name, clk):
            return self._cntx.sig(name, self.DATA_TYP, clk=clk, syncRst=self.rst, defVal=0)
        inReg = reg("inReg", self.inClk)
        outReg0 = reg("outReg0", self.outClk)
        outReg1 = reg("outReg1", self.outClk)
        
        
        c(self.inData, inReg)
        
        c(inReg, outReg0)
        c(outReg0, outReg1)
        
        c(outReg1, self.outData)
        
if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    print(toRtl(ClkSynchronizer))
