#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from hdl_toolkit.intfLvl import Param, Unit
from hwtLib.interfaces.amba import AxiStream


class SimpleUnitAxiStream(Unit):
    """
    Example of unit with axi stream interface
    """
    def _config(self):
        self.DATA_WIDTH = Param(8)

    def _declr(self):
        with self._asExtern(), self._paramsShared():
            self.a = AxiStream()
            self.b = AxiStream()

    def _impl(self):
        self.b ** self.a 
        
if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    print(toRtl(SimpleUnitAxiStream))
