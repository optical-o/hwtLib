from hwt.code import connect, log2ceil, Concat, Switch
from hwt.hdl.typeShortcuts import vec
from hwt.interfaces.std import Handshaked
from hwt.interfaces.utils import addClkRstn, propagateClkRstn
from hwt.synthesizer.param import Param
from hwtLib.abstract.busBridge import BusBridge
from hwtLib.amba.axi4Lite import Axi4Lite
from hwtLib.amba.axis_comp.builder import AxiSBuilder
from hwtLib.handshaked.fifo import HandshakedFifo
from hwtLib.handshaked.streamNode import StreamNode


class AxiResize(BusBridge):
    """
    Change DATA_WIDTH of axi interface

    .. hwt-schematic:: _example_AxiResize
    """

    def __init__(self, intfCls):
        self.intfCls = intfCls
        super(AxiResize, self).__init__()

    def _config(self):
        self.INTF_CLS = Param(self.intfCls)
        self.intfCls._config(self)
        self.OUT_DATA_WIDTH = Param(self.DATA_WIDTH)
        self.OUT_ADDR_WIDTH = Param(self.ADDR_WIDTH)
        self.MAX_TRANS_OVERLAP = Param(4)

    def _declr(self):
        addClkRstn(self)
        self.ALIGN_BITS_IN = log2ceil((self.DATA_WIDTH // 8) - 1)
        self.ALIGN_BITS_OUT = log2ceil((self.OUT_DATA_WIDTH // 8) - 1)
        assert self.ALIGN_BITS_IN <= self.ADDR_WIDTH, (self.ALIGN_BITS_IN, self.ADDR_WIDTH)
        assert self.ALIGN_BITS_OUT <= self.OUT_ADDR_WIDTH, (self.ALIGN_BITS_OUT, self.OUT_ADDR_WIDTH)

        with self._paramsShared():
            self.s = self.intfCls()

        with self._paramsShared():
            self.m = self.intfCls()._m()
            self.m.ADDR_WIDTH = self.OUT_ADDR_WIDTH
            self.m.DATA_WIDTH = self.OUT_DATA_WIDTH

    def propagate_addr(self, m_a, s_a):
        name_prefix = m_a._name + "_"
        AL_IN_W = self.ALIGN_BITS_IN
        AL_OUT_W = self.ALIGN_BITS_OUT
        ALIG_W = AL_OUT_W - AL_IN_W
        assert ALIG_W > 0, ALIG_W
        m_a = AxiSBuilder(self, m_a).buff().end

        align_fifo = HandshakedFifo(Handshaked)
        align_fifo.DATA_WIDTH = ALIG_W
        align_fifo.DEPTH = self.MAX_TRANS_OVERLAP
        setattr(self, name_prefix + "align_fifo", align_fifo)

        aligned_addr = Concat(m_a.addr[:AL_OUT_W], vec(0, AL_OUT_W))
        align_fifo.dataIn.data(m_a.addr[AL_OUT_W:AL_IN_W])

        connect(m_a, s_a, exclude={m_a.addr, m_a.valid, m_a.ready})
        StreamNode(
            masters=[m_a],
            slaves=[s_a, align_fifo.dataIn],
        ).sync()
        connect(aligned_addr, s_a.addr, fit=self.ADDR_WIDTH != self.OUT_ADDR_WIDTH)

        return align_fifo

    def connect_with_padding(self, src, src_range, dst, dst_range):
        src_h, src_l = src_range
        dst_h, dst_l = dst_range
        src_w = src._dtype.bit_length()
        dst_w = dst._dtype.bit_length()
        if dst_w < src_w:
            return dst(src[src_h:src_l])
        else:
            data = []
            if dst_h < dst_w:
                data.append(vec(0, dst_w - dst_h))
            data.append(src[src_h:src_l])
            if dst_l > 0:
                data.append(vec(0, dst_l))
            return dst(Concat(*data))

    def connect_shifted(self, src_ch, dst_ch, i):
        has_strb = hasattr(src_ch, "strb")
        has_keep = hasattr(src_ch, "keep")

        res = []
        if i == 0:
            res.append(connect(src_ch.data, dst_ch.data, fit=True))
            if has_strb:
                res.append(connect(src_ch.strb, dst_ch.strb, fit=True))
            if has_keep:
                res.append(connect(src_ch.keep, dst_ch.keep, fit=True))
        else:
            # i > 0
            dst_w = dst_ch.data._dtype.bit_length() // 8
            src_w = src_ch.data._dtype.bit_length() // 8
            if dst_w < src_w:
                assert src_w % dst_w == 0, (src_w, dst_w)
                dst_l, dst_h = 0, dst_w
                src_l, src_h = i * dst_w, (i + 1) * dst_w
            else:
                assert dst_w % src_w == 0
                dst_l, dst_h = i * src_w, (i + 1) * src_w
                src_l, src_h = 0, src_w

            c = self.connect_with_padding
            res.append(
                c(src_ch.data, (src_h * 8, src_l* 8), dst_ch.data, (dst_h * 8, dst_l* 8))
            )
            if has_strb:
                res.append(
                    c(src_ch.strb, (src_h, src_l), dst_ch.strb, (dst_h, dst_l))
                )
            if has_keep:
                res.append(
                    c(src_ch.keep, (src_h, src_l), dst_ch.keep, (dst_h, dst_l))
                )

        return res

    def select_data_word_from_ouput_word(self, m, s):
        w_align_fifo = self.propagate_addr(m.aw, s.aw)
        r_align_fifo = self.propagate_addr(m.ar, s.ar)
        AL_IN_W = self.ALIGN_BITS_IN
        AL_OUT_W = self.ALIGN_BITS_OUT
        ALIG_W = AL_OUT_W - AL_IN_W
        assert ALIG_W > 0, ALIG_W
        r_align_cases = []
        w_align_cases = []
        for i in range(2 ** ALIG_W):
            r_align_cases.append((i, self.connect_shifted(s.r, m.r, i)))
            w_align_cases.append((i, self.connect_shifted(m.w, s.w, i)))

        connect(m.w, s.w, exclude={m.w.data, m.w.strb, m.w.ready, m.w.valid})
        StreamNode(masters=[m.w, w_align_fifo.dataOut], slaves=[s.w]).sync()
        Switch(w_align_fifo.dataOut.data).addCases(w_align_cases)\
            .Default(
                # case which was unexpected or was filtered out by IN_ADDR_GRANULARITY
                s.w.data(None),
                s.w.strb(None),
            )

        connect(s.r, m.r, exclude={s.r.data, s.r.ready, s.r.valid})
        StreamNode(masters=[s.r, r_align_fifo.dataOut], slaves=[m.r]).sync()
        Switch(r_align_fifo.dataOut.data).addCases(r_align_cases)\
            .Default(
                # case which was unexpected or was filtered out by IN_ADDR_GRANULARITY
                m.r.data(None),
            )

        m.b(s.b)

    def _impl(self):
        m, s = self.m, self.s
        has_len = hasattr(s.ar, "len")
        DW = self.DATA_WIDTH
        OUT_DW = self.OUT_DATA_WIDTH
        if DW == OUT_DW and self.ADDR_WIDTH == self.OUT_ADDR_WIDTH:
            raise AssertionError("It is useless to use this convertor"
                                 " if the interface is of same size")

        if has_len:
            # Axi3/4, etc
            if DW <= OUT_DW:
                # always reading/writing less data than is max of output
                raise NotImplementedError()
            else:
                # requires split to multiple transactions on output
                raise NotImplementedError()
        else:
            # Axi4Lite, etc
            if DW == OUT_DW:
                # always reading/writing less data than is max of output
                if self.ADDR_WIDTH != self.OUT_ADDR_WIDTH:
                    connect(s.aw, m.aw, fit=True)
                    connect(s.ar, m.ar, fit=True)
                else:
                    m.aw(s.aw)
                    m.ar(s.ar)
                connect(s.w, m.w, fit=True)
                connect(m.r, s.r, fit=True)
                s.b(m.b)
            elif DW < OUT_DW:
                assert OUT_DW % DW == 0, (OUT_DW, DW)
                self.select_data_word_from_ouput_word(s, m)
            else:
                # requires split to multiple transactions on output
                raise NotImplementedError(DW, OUT_DW)
        propagateClkRstn(self)


def _example_AxiResize():
    u = AxiResize(Axi4Lite)
    u.DATA_WIDTH = 32
    u.OUT_DATA_WIDTH = 512
    return u


if __name__ == "__main__":
    from hwt.synthesizer.utils import toRtl
    u = _example_AxiResize()
    print(toRtl(u))
