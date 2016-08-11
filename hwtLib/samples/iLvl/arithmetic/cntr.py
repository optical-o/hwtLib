from hdl_toolkit.hdlObjects.typeShortcuts import vecT
from hdl_toolkit.interfaces.std import Signal
from hdl_toolkit.interfaces.utils import addClkRstn
from hdl_toolkit.synthesizer.codeOps import connect, If
from hdl_toolkit.synthesizer.interfaceLevel.unit import Unit
from hdl_toolkit.synthesizer.param import Param


class Cntr(Unit):
    def _config(self):
        self.DATA_WIDTH = Param(2)
        
    def _declr(self):
        with self._asExtern():
            addClkRstn(self)
            self.en = Signal()
            self.val = Signal(dtype=vecT(self.DATA_WIDTH))
        
    def _impl(self):
        reg = self._reg("counter", vecT(self.DATA_WIDTH), 0)
        
        If(self.en,
           connect(reg + 1, reg)
        ).Else(
           connect(reg, reg)
        )
        
        connect(reg, self.val)


if __name__ == "__main__": # alias python main function
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    # there is more of synthesis methods. toRtl() returns formated vhdl string
    print(toRtl(Cntr))