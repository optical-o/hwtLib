#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List

from pyMathBitPrecise.bit_utils import mask

from hwt.code import log2ceil, FsmBuilder, And, Or, If, ror, SwitchLogic, \
    connect, Concat
from hwt.hdl.types.bits import Bits
from hwt.hdl.types.defs import BIT
from hwt.hdl.types.enum import HEnum
from hwt.hdl.types.struct import HStruct
from hwt.interfaces.std import HandshakeSync
from hwt.interfaces.utils import propagateClkRstn, addClkRstn
from hwt.synthesizer.hObjList import HObjList
from hwt.synthesizer.param import Param
from hwt.synthesizer.unit import Unit
from hwtLib.handshaked.streamNode import StreamNode
from hwtLib.mem.cuckooHashTable_intf import CInsertIntf
from hwtLib.mem.hashTableCore import HashTableCore
from hwtLib.mem.hashTable_intf import LookupKeyIntf, LookupResultIntf, \
    HashTableIntf
from hwt.synthesizer.rtlLevel.rtlSignal import RtlSignal
from hwt.code_utils import rename_signal

ORIGIN_TYPE = HEnum("ORIGIN_TYPE", ["INSERT", "LOOKUP", "DELETE"])


# https://web.stanford.edu/class/cs166/lectures/13/Small13.pdf
class CuckooHashTable(HashTableCore):
    """
    Cuckoo hash uses more tables with different hash functions

    Lookup is performed in all tables at once and if item is found in any
    table. The item is found. Otherwise item is not in tables.
    lookup time: O(1)

    Insert has to first lookup if item is in any table. If any table contains invalid item.
    The item is stored there and insert operation is complete.
    If there was a valid item under this key in all tables. One is selected
    and it is swapped with current item. Insert process then repeats with this item.
    Until some invalid item (empty slot) is found.

    Inserting into table does not have to be successful and in this case,
    fsm ends up in infinite loop and it will be reinserting items for ever.
    insert time: O(inf)

    .. aafig::
                    +-------------------------------------------+
                    |                                           |
                    |    CuckooHashTable                        |
        insert      |                                lookupRes  |
        +--------------------------------------+  +------+      |
                    |                          |  |      |      |
                    |                          v  v      |      | lookupRes
        lookup      |                        +-------+   +----------->
        +----------------------------------->|       |   |      |
                    |  +-------------------->| stash |   |      |
                    |  |                +----+       |   |      |
         delete     |  |                v    +------++   |      |
        +--------------+            +-------+       |    |      |
                    |               | insert|     lookup |      |  insert, 
                    |               +----+--+       v    |      |  lookup,
                    |                 ^  |       +--------+     |  lookupRes
                    |                 |  +------>| tables +------------->
         clean      |   +--------+    |          +--------+     |
        +-------------->|cleanFSM+ ---+                         |
                    |   +--------+                              |
                    |                                           |
                    +-------------------------------------------+

    .. hwt-schematic::
    """

    def __init__(self):
        Unit.__init__(self)

    def _config(self):
        self.TABLE_SIZE = Param(32)
        self.DATA_WIDTH = Param(32)
        self.KEY_WIDTH = Param(8)
        self.LOOKUP_KEY = Param(False)
        self.TABLE_CNT = Param(2)
        self.MAX_LOOKUP_OVERLAP = Param(16)

    def _declr_outer_io(self):
        addClkRstn(self)
        assert self.TABLE_SIZE % self.TABLE_CNT == 0
        self.HASH_WIDTH = log2ceil(self.TABLE_SIZE // self.TABLE_CNT)

        with self._paramsShared():
            self.insert = CInsertIntf()
            self.lookup = LookupKeyIntf()
            self.lookupRes = LookupResultIntf()._m()
            self.lookupRes.HASH_WIDTH = self.HASH_WIDTH

        with self._paramsShared(exclude=({"DATA_WIDTH"}, set())):
            self.delete = CInsertIntf()
            self.delete.DATA_WIDTH = 0

        self.clean = HandshakeSync()

    def _declr(self):
        self._declr_outer_io()

        with self._paramsShared():
            self.tables = HObjList(
                HashTableIntf()._m()
                for _ in range(self.TABLE_CNT))

            for t in self.tables:
                t.ITEMS_CNT = self.TABLE_SIZE // self.TABLE_CNT
                t.LOOKUP_HASH = True

    def configure_tables(self, tables: List[HashTableCore]):
        """
        share the configuration with the table engines
        """
        for t in tables:
            t._updateParamsFrom(self)
            t.ITEMS_CNT = self.TABLE_SIZE // self.TABLE_CNT
            t.LOOKUP_HASH = True
        
    def clean_addr_iterator(self, en):
        lastAddr = self.TABLE_SIZE // self.TABLE_CNT - 1
        addr = self._reg("cleanupAddr",
                         Bits(log2ceil(lastAddr), signed=False),
                         def_val=0)
        last = addr._eq(lastAddr)
        If(en,
            If(last,
                addr(0)
            ).Else(
                addr(addr + 1)
           )
        )

        return addr, last

    def tables_insert_driver(self, state: RtlSignal, insertTargetOH: RtlSignal,
                             insertIndex: RtlSignal, stash: RtlSignal):
        """
        :param state: state register of main FSM
        :param insertTargetOH: index of table where insert should be performed,
            one hot encoding
        :param insertIndex: address for table where item should be placed
        :param stash: stash register
        """
        fsm_t = state._dtype
        for i, t in enumerate(self.tables):
            ins = t.insert
            ins.hash(insertIndex)
            ins.key(stash.key)

            if self.DATA_WIDTH:
                ins.data(stash.data)
            ins.vld(Or(state._eq(fsm_t.cleaning),
                       state._eq(fsm_t.lookupResAck) & 
                       insertTargetOH[i]))
            ins.item_vld(stash.item_vld)

    def tables_lookupRes_driver(self, resRead: RtlSignal, resAck: RtlSignal):
        """
        Control lookupRes interface for each table
        """
        tables = self.tables
        # one hot encoded index where item should be stored (where was found
        # or where is place)
        targetOH = self._reg("targetOH", Bits(self.TABLE_CNT, force_vector=True))

        res = [t.lookupRes for t in tables]
        # synchronize all lookupRes from all tables
        StreamNode(masters=res).sync(resAck)

        insertFinal = self._reg("insertFinal")
        # select empty space or victim which which current insert item
        # should be swapped with
        lookupResAck = StreamNode(masters=[t.lookupRes for t in tables]).ack()
        lookupFoundOH = [t.lookupRes.found for t in tables]
        isEmptyOH = [~t.lookupRes.occupied for t in tables]
        _insertFinal = Or(*lookupFoundOH, *isEmptyOH)

        If(resRead & lookupResAck,
            If(Or(*lookupFoundOH),
                targetOH(Concat(*reversed(lookupFoundOH)))
            ).Else(
                SwitchLogic(
                    [(isEmpty, targetOH(1 << i))
                     for i, isEmpty in enumerate(isEmptyOH)],
                    default=If(targetOH != 0,
                                targetOH(ror(targetOH, 1))
                            ).Else(
                                targetOH(1 << (self.TABLE_CNT - 1))
                            )
                )
            ),
            insertFinal(_insertFinal)
        )
        return lookupResAck, insertFinal, lookupFoundOH, targetOH

    def insert_addr_select(self, targetOH, state, cleanAddr):
        """
        Select a insert address
        """
        insertIndex = self._sig("insertIndex", Bits(self.HASH_WIDTH))
        If(state._eq(state._dtype.cleaning),
            insertIndex(cleanAddr)
        ).Else(
            SwitchLogic([(targetOH[i],
                          insertIndex(t.lookupRes.hash))
                         for i, t in enumerate(self.tables)],
                        default=insertIndex(None))
        )
        return insertIndex

    def stash_load(self, isIdle, stash, lookup_not_in_progress, another_lookup_possible):
        """
        load a stash register from lookup/insert/delete interface
        """
        lookup = self.lookup
        insert = self.insert
        delete = self.delete
        table_lookup_ack = StreamNode(slaves=[t.lookup for t in self.tables]).ack()
        lookup_currently_executed = stash.origin_op._eq(ORIGIN_TYPE.LOOKUP)
        If(isIdle,
            If(lookup_not_in_progress & self.clean.vld,
                stash.item_vld(0)
            ).Elif(lookup_not_in_progress & delete.vld,
                stash.key(delete.key),
                stash.origin_op(ORIGIN_TYPE.DELETE),
                stash.item_vld(0),
            ).Elif(lookup_not_in_progress & insert.vld,
                stash.origin_op(ORIGIN_TYPE.INSERT),
                stash.key(insert.key),
                stash.data(insert.data),
                stash.item_vld(1),
            ).Elif(lookup.vld & lookup.rd,
                stash.origin_op(ORIGIN_TYPE.LOOKUP),
                stash.key(lookup.key),
            ).Elif(table_lookup_ack,
                stash.origin_op(ORIGIN_TYPE.DELETE),  # need to set something else than lookup
                stash.key(None),
            )
        )
        cmd_priority = [self.clean, self.delete, self.insert, lookup]
        for i, intf in enumerate(cmd_priority):
            withLowerPrio = cmd_priority[:i]
            rd = And(isIdle, *[~x.vld for x in withLowerPrio])
            if intf is lookup:
                rd = rd & (~lookup_currently_executed |  # the stash not loaded yet
                     table_lookup_ack  # stash will be consumed
                    ) & another_lookup_possible
            else:
                rd = rd & lookup_not_in_progress

            intf.rd(rd)

    def tables_lookup_driver(self, state: RtlSignal, tableKey: RtlSignal, lookop_en: RtlSignal):
        """
        Connect a lookup ports of all tables
        """
        for t in self.tables:
            t.lookup.key(tableKey)

        # activate lookup only in lookup state (for insert/delete) or if idle and processing lookups
        fsm_t = state._dtype
        en = state._eq(fsm_t.lookup) | (state._eq(fsm_t.idle) & lookop_en)
        StreamNode(slaves=[t.lookup for t in self.tables]).sync(en)

    def lookupRes_driver(self, state: RtlSignal, lookupFoundOH: RtlSignal):
        """
        If lookup request comes from external interface "lookup" propagate results
        from tables to "lookupRes".
        """
        fsm_t = state._dtype
        lookupRes = self.lookupRes
        lookupResAck = StreamNode(masters=[t.lookupRes for t in self.tables]).ack()
        lookupRes.vld(state._eq(fsm_t.idle) & lookupResAck)

        SwitchLogic([(lookupFoundOH[i],
                      connect(t.lookupRes,
                              lookupRes,
                              exclude={lookupRes.vld,
                                       lookupRes.rd}))
                     for i, t in enumerate(self.tables)],
                    default=[
                        connect(self.tables[0].lookupRes,
                                lookupRes,
                                exclude={lookupRes.vld,
                                         lookupRes.rd})]
                    )

    def lookup_trans_cntr(self):
        """
        create a counter of pure lookup operations in progress
        """
        lookup = self.lookup
        lookupRes = self.lookupRes
        lookup_in_progress = self._reg("lookup_in_progress", Bits(log2ceil(self.MAX_LOOKUP_OVERLAP - 1)), def_val=0)
        lookup_trans = lookup.rd & lookup.vld
        lookupRes_trans = lookupRes.rd & lookupRes.vld

        If(lookup_trans & ~lookupRes_trans,
            lookup_in_progress(lookup_in_progress + 1)
        ).Elif(~lookup_trans & lookupRes_trans,
            lookup_in_progress(lookup_in_progress - 1)
        )
        return lookup_in_progress

    def _impl(self):
        propagateClkRstn(self)

        # stash is storage for item which is going to be swapped with actual
        stash_t = HStruct(
            (Bits(self.KEY_WIDTH), "key"),
            (Bits(self.DATA_WIDTH), "data"),
            (BIT, "item_vld"),
            (ORIGIN_TYPE, "origin_op"),
        )
        stash = self._reg("stash", stash_t, def_val={"origin_op": ORIGIN_TYPE.DELETE})

        cleanAck = self._sig("cleanAck")
        cleanAddr, cleanLast = self.clean_addr_iterator(cleanAck)
        lookupResRead = self._sig("lookupResRead")
        lookupResNext = self._sig("lookupResNext")
        (lookupResAck,
         insertFinal,
         lookupFound,
         targetOH) = self.tables_lookupRes_driver(lookupResRead,
                                                  lookupResNext)
        tables = self.tables
        lookupAck = StreamNode(slaves=[t.lookup for t in tables]).ack()
        insertAck = StreamNode(slaves=[t.insert for t in tables]).ack()

        lookup_in_progress = self.lookup_trans_cntr()
        lookup_not_in_progress = rename_signal(self,
            lookup_in_progress._eq(0) & (stash.origin_op != ORIGIN_TYPE.LOOKUP),
            "lookup_not_in_progress")
        
        # lookup is not blocking and does not use FSM bellow
        # this FSM handles only lookup for insert/delete
        fsm_t = HEnum("insertFsm_t", ["idle", "cleaning",
                                      "lookup", "lookupResWaitRd",
                                      "lookupResAck"])

        state = FsmBuilder(self, fsm_t, "insertFsm")\
            .Trans(fsm_t.idle,
                   # wait before lookup_in_progress reaches 0
                   # (new transactions should not be allowed if command has vld)
                   (lookup_not_in_progress & self.clean.vld, fsm_t.cleaning),
                   # before each insert suitable place has to be searched first
                   (lookup_not_in_progress & (self.insert.vld | self.delete.vld), fsm_t.lookup)
            ).Trans(fsm_t.cleaning,
                # walk all items and clean it's item_vlds
                (cleanAck & cleanLast, fsm_t.idle)
            ).Trans(fsm_t.lookup,
                # search and resolve in which table item
                # should be stored
                (lookupAck, fsm_t.lookupResWaitRd)
            ).Trans(fsm_t.lookupResWaitRd,
                # process result of lookup and
                # write data stash to tables if
                # required
                (lookupResAck, fsm_t.lookupResAck)
            ).Trans(fsm_t.lookupResAck,
                # process lookupRes, if we are going to insert on place where
                # valid item is, it has to
                # be stored
                (stash.origin_op._eq(ORIGIN_TYPE.DELETE), fsm_t.idle),
                # insert into specified table
                (insertAck & insertFinal, fsm_t.idle),
                (insertAck & ~insertFinal, fsm_t.lookup)
            ).stateReg

        cleanAck(StreamNode(slaves=[t.insert for t in tables]).ack() & 
                 state._eq(fsm_t.cleaning))
        lookupResRead(state._eq(fsm_t.lookupResWaitRd))
        lookupResNext(state._eq(fsm_t.lookupResAck) | (state._eq(fsm_t.idle) & self.lookupRes.rd))

        isIdle = state._eq(fsm_t.idle)
        self.stash_load(
            isIdle, stash,
            lookup_not_in_progress,
            lookup_in_progress != self.MAX_LOOKUP_OVERLAP - 1)
        insertIndex = self.insert_addr_select(targetOH, state, cleanAddr)
        self.tables_insert_driver(state, targetOH, insertIndex, stash)
        self.lookupRes_driver(state, lookupFound)
        self.tables_lookup_driver(state, stash.key, stash.origin_op._eq(ORIGIN_TYPE.LOOKUP))


if __name__ == "__main__":
    from hwt.synthesizer.utils import to_rtl_str
    u = CuckooHashTable()
    print(to_rtl_str(u))
