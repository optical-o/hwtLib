from hdl_toolkit.hdlObjects.typeShortcuts import vec
from hdl_toolkit.hdlObjects.types.enum import Enum
from hdl_toolkit.hdlObjects.types.typeCast import toHVal
from hdl_toolkit.interfaces.amba import AxiLite, RESP_OKAY
from hdl_toolkit.interfaces.utils import addClkRstn, log2ceil
from hdl_toolkit.synthesizer.codeOps import If, c, FsmBuilder, Or
from hdl_toolkit.synthesizer.param import evalParam
from hwtLib.abstract.busConverter import BusConverter

class AxiLiteConverter(BusConverter):
    """
    Axi lite converter generator
    """
    def _config(self):
        AxiLite._config(self)

    def _declr(self):
        with self._asExtern():
            addClkRstn(self)
            
            with self._paramsShared():
                self.axi = AxiLite()
            
            assert self.ADRESS_MAP[-1][0] < (2 ** evalParam(self.ADDR_WIDTH).val)
            self.decorateWithConvertedInterfaces()

    def readPart(self, awAddr, w_hs):
        DW_B = evalParam(self.DATA_WIDTH).val // 8 
        # build read data output mux
        def isMyAddr(addrSig, addr, size):
            return (addrSig >= addr) & (addrSig < (toHVal(addr) + (size * DW_B)))
        
        rSt_t = Enum('rSt_t', ['rdIdle', 'bramRd', 'rdData'])
        ar = self.axi.ar
        r = self.axi.r
        isBramAddr = self._sig("isBramAddr")
        rdataReg = self._reg("rdataReg", r.data._dtype)
        
        rSt = FsmBuilder(self, rSt_t, stateRegName='rSt')\
        .Trans(rSt_t.rdIdle,
            (ar.valid & ~isBramAddr & ~w_hs, rSt_t.rdData),
            (ar.valid & isBramAddr & ~w_hs, rSt_t.bramRd)
        ).Trans(rSt_t.bramRd,
            (~w_hs, rSt_t.rdData)
        ).Default(# Trans(rSt_t.rdData,
            (r.ready, rSt_t.rdIdle)
        ).stateReg
        
        arRd = rSt._eq(rSt_t.rdIdle)
        c(arRd & ~w_hs, ar.ready)
        
        c(rSt._eq(rSt_t.rdData), r.valid)
        c(RESP_OKAY, r.resp)
        
        # save ar addr
        arAddr = self._reg('arAddr', ar.addr._dtype) 
        If(ar.valid & arRd,
            c(ar.addr, arAddr)
        ).Else(
            arAddr._same()
        )
       
        
        _isInBramFlags = []
        rAssigTop = c(rdataReg, r.data)
        rregAssigTop = rdataReg._same()
        # rAssigTopCases =[]
        for addr, d in reversed(self._directlyMapped):
            # we are directly sending data from register
            rAssigTop = If(arAddr._eq(addr),
                           c(d.din, r.data)
                        ).Else(
                           rAssigTop
                        )

        bitForAligig = log2ceil(self.DATA_WIDTH // 8 - 1).val
        for addr, port, size in reversed(self._bramPortMapped):
            # map addr for bram ports
            _isMyAddr = isMyAddr(ar.addr, addr, size)
            _isInBramFlags.append(_isMyAddr)
            
            
            prioritizeWrite = isMyAddr(awAddr, addr, size) & w_hs
            
            a = self._sig("addr_forBram_" + port._name, awAddr._dtype)
            If(prioritizeWrite,
                c(awAddr - addr, a)
            ).Elif(rSt._eq(rSt_t.rdIdle),
                c(ar.addr - addr, a)
            ).Else(
                c(arAddr - addr, a)
            )
            
            addrHBit = port.addr._dtype.bit_length() 
            assert addrHBit + bitForAligig <= evalParam(self.ADDR_WIDTH).val
            
            c(a[(addrHBit + bitForAligig):bitForAligig], port.addr, fit=True)
            c(1, port.en)
            c(prioritizeWrite, port.we)
            
            rregAssigTop = If(_isMyAddr,
                c(port.dout, rdataReg)
            ).Else(
                rregAssigTop
            )

        if _isInBramFlags:
            c(Or(*_isInBramFlags), isBramAddr)
        else:
            c(0, isBramAddr)
        
    def writePart(self):
        sig = self._sig
        reg = self._reg
        addrWidth = evalParam(self.ADDR_WIDTH).val
        
        wSt_t = Enum('wSt_t', ['wrIdle', 'wrData', 'wrResp'])
        aw = self.axi.aw
        w = self.axi.w
        b = self.axi.b
        
        # write fsm
        wSt = FsmBuilder(self, wSt_t, "wSt")\
        .Trans(wSt_t.wrIdle,
            (aw.valid, wSt_t.wrData)
        ).Trans(wSt_t.wrData,
            (w.valid, wSt_t.wrResp)
        ).Default(# Trans(wSt_t.wrResp,
            (b.ready, wSt_t.wrIdle)
        ).stateReg
        
        aw_hs = sig('aw_hs')
        awAddr = reg('awAddr', aw.addr._dtype) 
        w_hs = sig('w_hs')
        c(wSt._eq(wSt_t.wrResp), b.valid)
  
        awRd = wSt._eq(wSt_t.wrIdle)
        c(awRd, aw.ready)
        wRd = wSt._eq(wSt_t.wrData)
        c(wRd, w.ready)
        
        c(vec(RESP_OKAY, 2), self.axi.b.resp)
        c(aw.valid & awRd, aw_hs) 
        c(w.valid & wRd, w_hs)
        
        # save aw addr
        If(awRd & aw.valid,
            c(aw.addr, awAddr)
        ).Else(
            c(awAddr, awAddr)
        )
        
        # output vld
        for addr, d in self._directlyMapped:
            out = d.dout
            c(w.data, out.data)
            c(w_hs & (awAddr._eq(vec(addr, addrWidth))), out.vld)
        
        for _, p, _ in self._bramPortMapped:
            c(w.data, p.din)
            
        return awAddr, w_hs    
    
    def _impl(self):
        awAddr, w_hs = self.writePart()
        self.readPart(awAddr, w_hs)
        
        

if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    u = AxiLiteConverter([(i * 4 , "data%d" % i) for i in range(2)] + 
                         [(3 * 4, "bramMapped", 32)])
    u.ADDR_WIDTH.set(8)
    u.DATA_WIDTH.set(32)
    
    print(toRtl(u))
    