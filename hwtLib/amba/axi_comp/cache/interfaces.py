from hwt.interfaces.agents.handshaked import HandshakedAgent
from hwt.interfaces.std import Handshaked, VectSignal, Signal
from hwt.synthesizer.interface import Interface
from hwt.synthesizer.param import Param
from ipCorePackager.constants import DIRECTION
from pycocotb.hdlSimulator import HdlSimulator

from hwtLib.amba.axi3Lite import Axi3Lite_addr, Axi3Lite_r


class AxiStoreBufferWriteIntf(Handshaked):
    """
    An interface which is used to push write data to a AxiStoreBuffer
    """

    def _config(self):
        Handshaked._config(self)
        self.ADDR_WIDTH = Param(32)

    def _declr(self):
        Handshaked._declr(self)
        self.addr = VectSignal(self.ADDR_WIDTH)
        self.mask = VectSignal(self.DATA_WIDTH // 8)

    def _initSimAgent(self, sim: HdlSimulator):
        self._ag = AxiStoreBufferWriteIntfAgent(sim, self)


class AxiStoreBufferWriteIntfAgent(HandshakedAgent):

    def get_data(self):
        i = self.intf
        return (i.addr.read(), i.data.read(), i.mask.read())

    def set_data(self, data):
        i = self.intf
        if data is None:
            a, d, m = (None, None, None)
        else:
            a, d, m = data
        i.addr.write(a)
        i.data.write(d)
        i.mask.write(m)


class AxiStoreBufferWriteTmpIntf(AxiStoreBufferWriteIntf):
    """
    Interface for tmp input register on store buffer write input
    """

    def _config(self):
        AxiStoreBufferWriteIntf._config(self)
        self.ITEMS = Param(64)

    def _declr(self):
        AxiStoreBufferWriteIntf._declr(self)
        self.cam_lookup = VectSignal(self.ITEMS)

    def _initSimAgent(self, sim: HdlSimulator):
        raise NotImplementedError()


class AxiStoreBufferReadIntf(Interface):
    """
    An interface which is used to speculatively read data from AxiStoreBuffer
    """

    def _config(self):
        self.ADDR_WIDTH = Param(32)
        self.DATA_WIDTH = Param(64)

    def _declr(self):
        self.a = Axi3Lite_addr()
        self.r_data_available = Handshaked()
        self.r_data_available.DATA_WIDTH = 1
        self.r = Axi3Lite_r()

    def _initSimAgent(self, sim: HdlSimulator):
        raise NotImplementedError()


class AddrDataIntf(Interface):

    def _config(self):
        self.ADDR_WIDTH = Param(32)
        self.DATA_WIDTH = Param(64)

    def _declr(self):
        self.addr = VectSignal(self.ADDR_WIDTH)
        self.data = VectSignal(self.DATA_WIDTH, masterDir=DIRECTION.IN)
