#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from hwt.code import If, Concat, connect
from hwt.code_utils import rename_signal
from hwt.hdl.types.bits import Bits
from hwt.interfaces.std import VldSynced
from hwt.interfaces.utils import addClkRstn, propagateClkRstn
from hwt.serializer.mode import serializeParamsUniq
from hwt.synthesizer.param import Param
from hwt.synthesizer.rtlLevel.rtlSignal import RtlSignal
from hwt.synthesizer.unit import Unit
from hwtLib.amba.axi4 import Axi4, Axi4_r
from hwtLib.amba.axi_comp.lsu.write_aggregator_write_dispatcher import AxiWriteAggregatorWriteDispatcher
from hwtLib.amba.axis_comp.fifoCopy import AxiSFifoCopy, AxiSRegCopy
from hwtLib.amba.axis_comp.reg import AxiSReg
from hwtLib.handshaked.reg import HandshakedReg
from hwtLib.handshaked.streamNode import StreamNode
from hwtLib.logic.binToOneHot import binToOneHot
from hwtLib.logic.oneHotToBin import oneHotToBin
from hwtLib.mem.cam import Cam
from pyMathBitPrecise.bit_utils import apply_set_and_clear


@serializeParamsUniq
class AxiReadAggregator(Unit):
    """
    This is a component which reduces reads from same address.

    This component has several slots for read transactions, Each slot has it's own address record in CAM which is used
    to detect reads from same address, if the read is from same address which is currently being loaded. The read thread
    is put to sleep until data for previous read is received. After it is received it is copied as a response also
    for this transaction.

    If there is a read request the write buffer is checked first. If it does not contain requested cacheline the read request is
    forwarded to slave insterface ("s").

    This component also tries to provide as fresh data as possible. This means that pending read transaction
    can be potentially be cancelled and finished from the write transaction. If this happens we need to mark this read transaction to be dropped.
    
    We do this to minimise need for consystency check on user side of the component. Thanks to this, there is a maximum number of write transactions
    which have to be checked for access conflicts on user side. This number corresponds to a latency of a write port on a StoreQueue side,
    which is usually 2. If these write transactions are used to update the read data, the read data are asserted to be a last written value
    on that specified address. 

    .. hwt-schematic::
    """

    def _config(self):
        Axi4._config(self)
        self.CACHE_LINE_SIZE = Param(64)  # [B]

    def _declr(self):
        AxiWriteAggregatorWriteDispatcher.precompute_constants(self)
        addClkRstn(self)
        with self._paramsShared():
            self.s = Axi4()
            self.m = Axi4()._m()
    
            if self.BUS_WORDS_IN_CACHE_LINE > 1:
                fb = AxiSFifoCopy(Axi4_r)
                fb.DEPTH = 2 * self.BUS_WORDS_IN_CACHE_LINE
            else:
                fb = AxiSRegCopy(Axi4_r)
            self.frame_buff = fb

        ac = self.addr_cam = Cam()
        ac.ITEMS = 2 ** self.ID_WIDTH
        ac.USE_VLD_BIT = False
        ac.KEY_WIDTH = self.CACHE_LINE_ADDR_WIDTH

        for i in [self.s, self.m]:
            i.HAS_W = False

    def read_data_section(self, read_ack: RtlSignal,
                          waiting_transaction_id: RtlSignal,
                          waiting_transaction_vld: RtlSignal,
                          data_copy_override: VldSynced):
        s = self.s
        m = self.m
        
        fb = self.frame_buff
        
        data_out_node = StreamNode([fb.dataOut], [s.r])
        data_out_node.sync()
        read_ack(data_out_node.ack())
        
        fb.dataOut_copy_frame(
            (fb.dataOut.valid & fb.dataOut.last & waiting_transaction_vld[fb.dataOut.id]) |
            data_copy_override.vld
        )
        If(data_copy_override.vld,
            fb.dataOut_replacement_id(data_copy_override.data)
        ).Else(
            fb.dataOut_replacement_id(waiting_transaction_id[fb.dataOut.id])
        )
        connect(fb.dataOut, s.r, exclude={s.r.valid, s.r.ready})

        StreamNode(
            [m.r],
            [fb.dataIn],
        ).sync()
        connect(m.r, fb.dataIn, exclude={m.r.valid, m.r.ready})

    def add_addr_cam_out_reg(self, item_vld:RtlSignal):
        addr_cam = self.addr_cam
        addr_cam_out = addr_cam.out #HsBuilder(self, addr_cam.out).buff(1).end
        addr_cam_out_reg = HandshakedReg(addr_cam.out.__class__)
        addr_cam_out_reg._updateParamsFrom(addr_cam_out)
        self.addr_cam_out_reg = addr_cam_out_reg
        connect(addr_cam_out, addr_cam_out_reg.dataIn, exclude=[addr_cam_out.data])
        addr_cam_out_reg.dataIn.data(addr_cam_out.data & item_vld)
        addr_cam_out = addr_cam_out_reg.dataOut
        return addr_cam_out

    def read_request_section(self, read_ack: RtlSignal,
                             item_vld: RtlSignal,
                             waiting_transaction_id: RtlSignal,
                             waiting_transaction_vld: RtlSignal,
                             data_copy_override: VldSynced):
        s = self.s
        m = self.m
        addr_cam = self.addr_cam
        ITEMS = self.addr_cam.ITEMS
        addr_cam_out = self.add_addr_cam_out_reg(item_vld)
        
        with self._paramsShared():
            s_ar_tmp = self.s_ar_tmp = AxiSReg(s.AR_CLS)

        last_cam_insert_match = self._reg("last_cam_insert_match", Bits(ITEMS), def_val=0)
        match_res = rename_signal(
            self,
            item_vld &
            (addr_cam_out.data | last_cam_insert_match) &
            ~waiting_transaction_vld,
            "match_res")
        blocking_access = rename_signal(
            self,
            s.ar.valid & 
            (
                item_vld[s.ar.id] |
                (s_ar_tmp.dataOut.valid & (s.ar.id._eq(s_ar_tmp.dataOut.id)))
            ),
            "blocking_access")
        s_ar_node = StreamNode(
            [s.ar],
            [addr_cam.match, s_ar_tmp.dataIn],
        )
        s_ar_node.sync(~blocking_access)
        # s_ar_node_ack = s_ar_node.ack() & ~blocking_access
        connect(s.ar, s_ar_tmp.dataIn, exclude={s.ar.valid, s.ar.ready})
        
        parent_transaction_id = oneHotToBin(self, match_res, "parent_transaction_id")
        
        m_ar_node = StreamNode(
            [s_ar_tmp.dataOut, addr_cam_out],
            [m.ar],
            extraConds={m.ar: match_res._eq(0)},
            skipWhen={m.ar: (match_res != 0)}
        )
        m_ar_node.sync()
        connect(s_ar_tmp.dataOut, m.ar, exclude={m.ar.valid, m.ar.ready})
        addr_cam.match.data(s.ar.addr[:self.CACHE_LINE_OFFSET_BITS])
        ar_ack = rename_signal(self, m_ar_node.ack(), "ar_ack")
        
        # insert into cam on empty position specified by id of this transaction
        addr_cam.write.addr(s_ar_tmp.dataOut.id)
        addr_cam.write.data(s_ar_tmp.dataOut.addr[:self.CACHE_LINE_OFFSET_BITS])
        addr_cam.write.vld(addr_cam_out.vld)
        #If(s_ar_node_ack,
        last_cam_insert_match(binToOneHot(
            s_ar_tmp.dataOut.id,
            en=~blocking_access &
               s.ar.valid &
               s_ar_tmp.dataOut.valid &
               s_ar_tmp.dataOut.addr[:self.CACHE_LINE_OFFSET_BITS]._eq(s.ar.addr[:self.CACHE_LINE_OFFSET_BITS])
        ))
        #)

        item_vld_next = []
        waiting_transaction_vld_next = []

        for trans_id in range(ITEMS):
            # it becomes ready if we are requested for it on "s" interface
            this_trans_start = s_ar_tmp.dataOut.id._eq(trans_id) & \
                (data_copy_override.vld | ar_ack)
            # item becomes invalid if we read last data word
            this_trans_end = read_ack & s.r.id._eq(trans_id) & s.r.last
            this_trans_end = rename_signal(self, this_trans_end, "this_trans_end%d" % trans_id)
            this_transaction_vld = apply_set_and_clear(item_vld[trans_id], this_trans_start, this_trans_end)
            item_vld_next.append(this_transaction_vld)

            waiting_transaction_start = (
                ar_ack & 
                (match_res != 0) & 
                parent_transaction_id._eq(trans_id) &
                ~this_trans_end
            )
            # note: this_trans_end in this context is for parent transactio
            # which was not started just now, so it may be ending just now 
            waiting_transaction_start = rename_signal(self,  waiting_transaction_start, "waiting_transaction_start%d" % trans_id)
            _waiting_transaction_vld = apply_set_and_clear(
                waiting_transaction_vld[trans_id],
                waiting_transaction_start,
                this_trans_end)
            _waiting_transaction_vld = rename_signal(self, _waiting_transaction_vld, "waiting_transaction_vld%d" % trans_id)
            waiting_transaction_vld_next.append(_waiting_transaction_vld)

        item_vld(Concat(*reversed(item_vld_next)))
        waiting_transaction_vld(Concat(*reversed(waiting_transaction_vld_next)))
        
        If(self.clk._onRisingEdge(),
            If((match_res != 0) & ar_ack,
                waiting_transaction_id[parent_transaction_id](s_ar_tmp.dataOut.id)
            )
        )
        
        # parent transaction is finishing just now
        # we need to quickly grab the data in data buffer and copy it also 
        # for this transaction
        data_copy_override.vld(
            s_ar_tmp.dataOut.valid & 
            read_ack & 
            (match_res != 0) & 
            s.r.id._eq(parent_transaction_id) & 
            s.r.last)
        data_copy_override.data(s_ar_tmp.dataOut.id)
        

    def _impl(self):
        ITEMS = self.addr_cam.ITEMS
        item_vld = self._reg("item_vld", Bits(ITEMS), def_val=0)
        waiting_transaction_id = self._sig("waiting_transaction_id", self.s.ar.id._dtype[ITEMS])
        waiting_transaction_vld = self._reg("waiting_transaction_vld", Bits(ITEMS), def_val=0)
        read_ack = self._sig("read_ack")
        # if the parent transaction is about to finish how we need to copy the response now
        data_copy_override = VldSynced()
        data_copy_override.DATA_WIDTH = self.ID_WIDTH
        self.data_copy_override = data_copy_override
        
        self.read_request_section(
            read_ack, item_vld, waiting_transaction_id, waiting_transaction_vld,
            data_copy_override)
        self.read_data_section(
            read_ack, waiting_transaction_id, waiting_transaction_vld, data_copy_override)
        propagateClkRstn(self)


if __name__ == "__main__":
    from hwt.synthesizer.utils import to_rtl_str
    u = AxiReadAggregator()

    print(to_rtl_str(u))
