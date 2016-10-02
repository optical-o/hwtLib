#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from hdl_toolkit.hdlObjects.typeShortcuts import vecT
from hdl_toolkit.hdlObjects.types.array import Array
from hdl_toolkit.interfaces.std import Signal, Clk
from hdl_toolkit.synthesizer.codeOps import connect, If
from hdl_toolkit.synthesizer.interfaceLevel.unit import Unit


class SimpleAsyncRam(Unit):
    """
    Note that there is no such a thing in hw yet...
    """
    def _declr(self):
        with self._asExtern():
            self.addr_in = Signal(dtype=vecT(2))
            self.din = Signal(dtype=vecT(8))

            self.addr_out = Signal(dtype=vecT(2))
            self.dout = Signal(dtype=vecT(8))
        
    def _impl(self):
        self._ram = ram = self._sig("ram_data", Array(vecT(8), 4))
        connect(ram[self.addr_out], self.dout),
        connect(self.din, ram[self.addr_in])  

class SimpleSyncRam(SimpleAsyncRam):
    def _declr(self):
        super()._declr()
        with self._asExtern():
            self.clk = Clk()
    
    def _impl(self):
        self._ram = ram = self._sig("ram_data", Array(vecT(8), 4))
        
        If(self.clk._onRisingEdge(),
           self.dout ** ram[self.addr_out],
           ram[self.addr_in] ** self.din  
        )


if __name__ == "__main__":  # alias python main function
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    # there is more of synthesis methods. toRtl() returns formated vhdl string
    print(toRtl(SimpleSyncRam))
