from hdl_toolkit.bitmask import Bitmask
from hdl_toolkit.hdlObjects.typeShortcuts import vecT, hBit, vec
from hdl_toolkit.hdlObjects.types.enum import Enum
from hdl_toolkit.interfaces.std import Signal, VldSynced
from hdl_toolkit.interfaces.utils import addClkRstn
from hdl_toolkit.synthesizer.codeOps import c, If, Switch, FsmBuilder
from hdl_toolkit.synthesizer.interfaceLevel.unit import Unit
from hdl_toolkit.synthesizer.param import Param, evalParam
from hwtLib.interfaces.amba import AxiStream


class AxiSSampler(Unit):
    """    
        Samples values of a source into the output AXI-Stream
        interface. Samples are read from the sample interface.
        
        Sampling is done on request, ie. by asserting REQ.
        The value is sampled as soon as possible (may block
        if SAMPLE_VLD is low). The BUSY signal informs that
        the unit is blocking and waiting for SAMPLE_VLD high.
        
        The unit blocks (BUSY) also when the M_TREADY is low.
        In that case, the SAMPLE_DI value is saved internally.
        Ie. the sampled value always correlates as much as
        possible to the time when REQ has been asserted.
        
        @attention: last is always set
        @attention: strb is always -1
    """
    def _config(self):
        self.DATA_WIDTH = Param(32)
        self.SAMPLE_WIDTH = Param(32)

    def _declr(self):
        with self._asExtern():
            addClkRstn(self)
            
            self.req = Signal()
            self.busy = Signal()
            self.done = Signal()
            
            self.out = AxiStream()
            self.out._replaceParam('DATA_WIDTH', self.DATA_WIDTH)
            
            self.sample = VldSynced()
            self.sample._replaceParam('DATA_WIDTH', self.SAMPLE_WIDTH)
        
    def _impl(self):
        assert(evalParam(self.DATA_WIDTH).val >= evalParam(self.SAMPLE_WIDTH).val) 
        
        stT = Enum("st_t", ["stIdle", "stBusy", "stBusyHold"])

        sample = self._reg('sample', vecT(self.SAMPLE_WIDTH))
        sample_ce = self._sig("sample_ce")
        
        # reg_samplep
        If(sample_ce,
           c(self.sample.data, sample, fit=True)
        ).Else(
           sample._same()
        )
        
        # shortcuts
        sampleIn = self.sample
        out = self.out
        req = self.req
        
        # fsm_next
        st = FsmBuilder(self, stT)\
        .Trans(stT.stIdle,
            (req & ~sampleIn.vld, stT.stBusy), 
            (req & out.ready, stT.stBusyHold)
        ).Trans(stT.stBusy,
            (sampleIn.vld & out.ready, stT.stIdle),
            (sampleIn.vld, stT.stBusyHold)
        ).Trans(stT.stBusyHold,
            (out.ready, stT.stIdle)
        ).stateReg
        
        
        # fsm_output
        sample_ce ** ((sampleIn.vld & ~out.ready) 
                       & ((st._eq(stT.stIdle) & req) 
                            | st._eq(stT.stBusy)))
        
        If(st._eq(stT.stBusyHold),
           c(sample, out.data, fit=True)
        ).Else(
           c(sampleIn.data, out.data, fit=True)
        )
        self.busy ** (st != stT.stIdle)
        
        strbw = out.strb._dtype.bit_length()
        c(vec(Bitmask.mask(strbw), strbw), out.strb)
        c(hBit(1), out.last)
        Switch(st)\
        .Case(stT.stIdle,
            If(req & sampleIn.vld,
               out.valid ** 1
            ).Else(
               out.valid ** 0
            ),
            self.done ** (req & sampleIn.vld & out.ready)
        ).Case(stT.stBusy,
            out.valid ** sampleIn.vld,
            c(sampleIn.vld & out.ready, self.done)
        ).Case(stT.stBusyHold,
           out.valid ** 1,
           self.done ** out.ready 
        )
        
if __name__ == "__main__":
    from hdl_toolkit.synthesizer.shortcuts import toRtl
    print(toRtl(AxiSSampler)) 
        
        
        
