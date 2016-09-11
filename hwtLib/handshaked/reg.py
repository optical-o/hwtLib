from hdl_toolkit.interfaces.std import Handshaked
from hdl_toolkit.interfaces.utils import addClkRstn
from hdl_toolkit.synthesizer.codeOps import If, c
from hwtLib.handshaked.compBase import HandshakedCompBase 


class HandshakedReg(HandshakedCompBase):
    """
    Register for Handshaked interface
    """
    def _declr(self):
        with self._asExtern():
            addClkRstn(self)
            with self._paramsShared():
                self.dataIn = self.intfCls()
                self.dataOut = self.intfCls()
    
    def _impl(self):
        
        isOccupied = self._reg("isOccupied", defVal=0)
        regs_we = self._sig('reg_we')
        
        vld = self.getVld
        rd = self.getRd
        
        m = self.dataOut
        s = self.dataIn

        for iin, iout in zip(self.getData(s), self.getData(m)):
            assert(not iin._interfaces)  # has not subintefraces (Not implemented)
            
            r = self._reg('reg_' + iin._name, iin._dtype)
            
            If(regs_we,
                r ** iin
            )
            
            iout ** r

        If(isOccupied,
            If(rd(m) & ~vld(s),
                isOccupied ** 0
            )
        ).Else(
            If(vld(s),
               isOccupied ** 1
            )
        )
        
        If(isOccupied,
           c(rd(m), rd(s)) ,
           vld(m) ** 1,
           regs_we ** (vld(s) & rd(m))
        ).Else(
           rd(s) ** 1,
           vld(m) ** 0,
           regs_we ** vld(s)
        )

if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    u = HandshakedReg(Handshaked)
    
    print(toRtl(u))
