from typing import List, Tuple

from hwt.hdl.types.structUtils import HStruct_unpack
from hwt.interfaces.std import Signal, VectSignal
from hwt.pyUtils.arrayQuery import iter_with_last
from hwt.synthesizer.param import Param
from hwt.synthesizer.vectorUtils import iterBits
from hwtLib.amba.axi_intf_common import Axi_user, Axi_id, Axi_hs, Axi_strb
from hwtLib.amba.sim.agentCommon import BaseAxiAgent
from hwtLib.types.ctypes import uint8_t
from ipCorePackager.intfIpMeta import IntfIpMeta
from pyMathBitPrecise.bit_utils import mask, selectBit,\
    selectBitRange, setBit
from pycocotb.hdlSimulator import HdlSimulator


# http://www.xilinx.com/support/documentation/ip_documentation/ug761_axi_reference_guide.pdf
class AxiStream(Axi_hs, Axi_id, Axi_user, Axi_strb):
    """
    AMBA AXI-stream interface

    :ivar IS_BIGENDIAN: Param which specifies if interface uses bigendian
        byte order or litleendian byte order

    :ivar HAS_STRB: if set strb signal is present
    :ivar HAS_KEEP: if set keep signal is present
    :ivar ID_WIDTH: if > 0 id signal is present and this is it's width
    :ivar DEST_WIDTH: if > 0 dest signal is present and this is it's width

    :attention: no checks are made for endianity, this is just information
    :note: bigendian for interface means that items which are send through
        this interface have reversed byte endianity.
        That means that most significant byte is is on lower address
        than les significant ones
        f.e. litle endian value 0x1a2b will be 0x2b1a
        but iterface itselelf is not reversed in any way

    :ivar DATA_WIDTH: Param which specifies width of data signal
    :ivar id: optional signal wich specifies id of transaction
    :ivar dest: optional signal which specifies destination of transaction
    :ivar data: main data signal
    :ivar keep: optional signal which signalize which bytes
                should be keept and which should be discarted
    :ivar strb: optional signal which signalize which bytes are valid
    :ivar last: signal which if high this data is last in this frame
    """

    def _config(self):
        self.IS_BIGENDIAN = Param(False)
        self.USE_STRB = Param(False)
        self.USE_KEEP = Param(False)

        Axi_id._config(self)
        self.DEST_WIDTH = Param(0)
        self.DATA_WIDTH = Param(64)
        Axi_user._config(self)

    def _declr(self):
        Axi_id._declr(self)

        if self.DEST_WIDTH:
            self.dest = VectSignal(self.DEST_WIDTH)

        self.data = VectSignal(self.DATA_WIDTH)

        if self.USE_STRB:
            Axi_strb._declr(self)

        if self.USE_KEEP:
            self.keep = VectSignal(self.DATA_WIDTH // 8)

        Axi_user._declr(self)
        self.last = Signal()

        super(AxiStream, self)._declr()

    def _getIpCoreIntfClass(self):
        return IP_AXIStream

    def _initSimAgent(self, sim: HdlSimulator):
        self._ag = AxiStreamAgent(sim, self)


class AxiStreamAgent(BaseAxiAgent):
    """
    Simulation agent for :class:`.AxiStream` interface

    input/output data stored in list under "data" property
    data contains tuples

    Format of data tules is derived from signals on AxiStream interface
    Order of values coresponds to definition of interface signals.
    If all signals are present fotmat of tuple will be
    (id, dest, data, strb, keep, user, last)


    :ivar _signals: tuple of data signals of this interface
    :ivar _sigCnt: len(_signals)
    """

    def __init__(self, sim: HdlSimulator, intf: AxiStream, allowNoReset=False):
        BaseAxiAgent.__init__(self, sim, intf, allowNoReset=allowNoReset)

        signals = []
        for i in intf._interfaces:
            if i is not intf.ready and i is not intf.valid:
                signals.append(i)
        self._signals = tuple(signals)
        self._sigCnt = len(signals)

    def get_data(self):
        return tuple(sig.read() for sig in self._signals)

    def set_data(self, data):
        if data is None:
            for sig in self._signals:
                sig.write(None)
        else:
            assert len(data) == self._sigCnt, (len(data),
                                               self._signals,
                                               self.intf._getFullName())
            for sig, val in zip(self._signals, data):
                sig.write(val)


def packAxiSFrame(dataWidth, structVal, withStrb=False):
    """
    pack data of structure into words on axis interface
    """
    if withStrb:
        byte_cnt = dataWidth // 8

    words = iterBits(structVal, bitsInOne=dataWidth,
                     skipPadding=False, fillup=True)
    for last, d in iter_with_last(words):
        assert d._dtype.bit_length() == dataWidth, d._dtype.bit_length()
        if withStrb:
            word_mask = 0
            for B_i in range(byte_cnt):
                m = selectBitRange(d.vld_mask, B_i * 8, 8)
                if m == 0xff:
                    word_mask = setBit(word_mask, B_i)
                else:
                    assert m == 0, ("Each byte has to be entirely valid"
                                    " or entirely invalid,"
                                    " because of mask granularity", m)
            yield (d, word_mask, last)
        else:
            yield (d, last)


def unpackAxiSFrame(structT, frameData, getDataFn=None, dataWidth=None):
    """
    opposite of packAxiSFrame
    """
    if getDataFn is None:

        def _getDataFn(x):
            return x[0]

        getDataFn = _getDataFn

    return HStruct_unpack(structT, frameData, getDataFn, dataWidth)


def _axis_recieve_bytes(ag_data, D_B, use_keep, offset=0) -> Tuple[int, List[int]]:
    offset = None
    data_B = []
    last = False
    first = True
    mask_all = mask(D_B)
    while ag_data:
        _d = ag_data.popleft()
        if use_keep:
            data, keep, last = _d
            keep = int(keep)
        else:
            data, last = _d
            keep = mask_all

        last = int(last)
        assert keep > 0
        if offset is None:
            # first iteration
            # expecting potential 0s in keep and the rest 1
            for i in range(D_B):
                # i represents number of 0 from te beginning of of the keep
                # value
                if keep & (1 << i):
                    offset = i
                    break
            assert offset is not None, keep
        for i in range(D_B):
            if selectBit(keep, i):
                d = selectBitRange(data.val, i * 8, 8)
                if selectBitRange(data.vld_mask, i * 8, 8) != 0xff:
                    raise AssertionError(
                        "Data not valid but should be"
                        " based on strb/keep B_i:%d, 0x%x, 0x%x" % (i, keep, data.vld_mask))
                data_B.append(d)

        if first:
            offset_mask = mask(offset)
            assert offset_mask & keep == 0, (offset_mask, keep)
            first = False
        elif not last:
            assert keep == mask_all, keep
        if last:
            break

    if not last:
        if data_B:
            raise ValueError("Unfinished frame", data_B)
        else:
            raise ValueError("No frame available")

    return offset, data_B


def axis_recieve_bytes(axis: AxiStream) -> Tuple[int, List[int]]:
    """
    Read data from AXI Stream agent in simulation
    and use keep signal to mask out unused bytes
    """
    ag_data = axis._ag.data
    D_B = axis.DATA_WIDTH // 8
    if axis.ID_WIDTH:
        raise NotImplementedError()
    if axis.USER_WIDTH:
        raise NotImplementedError()
    if axis.USE_KEEP and axis.USE_STRB:
        raise NotImplementedError()
    use_keep = axis.USE_KEEP | axis.USE_STRB
    return _axis_recieve_bytes(ag_data, D_B, use_keep)


def _axis_send_bytes(axis: AxiStream, data_B: List[int], withStrb, offset)\
        -> List[Tuple[int, int, int]]:
    t = uint8_t[len(data_B) + offset]
    # :attention: strb signal is reinterpreted as a keep signal
    return packAxiSFrame(axis.DATA_WIDTH, t.from_py(
        [None for _ in range(offset)] + data_B),
        withStrb=withStrb)


def axis_send_bytes(axis: AxiStream, data_B: List[int], offset=0) -> None:
    """
    :param axis: AxiStream master which is driver from the simulation
    :param data_B: bytes to send
    :param offset: number of empty bytes which should be added before data
        in frame (and use keep signal to mark such a bytes)
    """
    if axis.ID_WIDTH:
        raise NotImplementedError()
    if axis.USER_WIDTH:
        raise NotImplementedError()
    if axis.USE_KEEP and axis.USE_STRB:
        raise NotImplementedError()
    withStrb = axis.USE_KEEP | axis.USE_STRB
    f = _axis_send_bytes(axis, data_B, withStrb, offset)
    axis._ag.data.extend(f)


class IP_AXIStream(IntfIpMeta):
    """
    Class which specifies how to describe AxiStream interfaces in IP-core
    """

    def __init__(self):
        super().__init__()
        self.name = "axis"
        self.quartus_name = "axi4stream"
        self.version = "1.0"
        self.vendor = "xilinx.com"
        self.library = "interface"
        self.map = {
            'id': "TID",
            'dest': "TDEST",
            'data': "TDATA",
            'strb': "TSTRB",
            'keep': "TKEEP",
            'user': 'TUSER',
            'last': "TLAST",
            'valid': "TVALID",
            'ready': "TREADY"
        }
        self.quartus_map = {
            k: v.lower() for k, v in self.map.items()
        }
