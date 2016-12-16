#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from hdl_toolkit.hdlObjects.typeShortcuts import hInt
from hdl_toolkit.intfLvl import Unit, Param
from hwtLib.interfaces.amba import AxiStream


class SimpleSubunit(Unit):
    def _config(self):
        self.DATA_WIDTH = Param(8)
        
    def _declr(self):
        with self._paramsShared():
            self.c = AxiStream()
            self.d = AxiStream()
        
    def _impl(self):
        self.d ** self.c

class InterfaceArraySample2(Unit):
    """
    Example unit which contains two subuints (u0 and u1) 
    and two array interfaces (a and b)
    first items of this interfaces are connected to u0
    second to u1
    """
    def _config(self):
        self.DATA_WIDTH = Param(8)
        
    def _declr(self):
        LEN = hInt(2)
        with self._paramsShared():
            self.a = AxiStream(multipliedBy=LEN)
            self.b = AxiStream(multipliedBy=LEN)
    
            self.u0 = SimpleSubunit() 
            self.u1 = SimpleSubunit()
            # self.u2 = SimpleSubunit()
        
    def _impl(self):
        
        self.u0.c ** self.a[0]
        self.u1.c ** self.a[1]
        # u2in = connect(a[2], u2.c)
    
        self.b[0] ** self.u0.d 
        self.b[1] ** self.u1.d
        # u2out = connect(u2.d, b[2])
        
if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    print(
        toRtl(InterfaceArraySample2())
    )
