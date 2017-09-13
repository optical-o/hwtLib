#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, List, Union

from hwt.code import log2ceil, If, Concat
from hwt.hdlObjects.frameTmpl import FrameTmpl
from hwt.hdlObjects.frameTmplUtils import ChoicesOfFrameParts
from hwt.hdlObjects.transPart import TransPart
from hwt.hdlObjects.transTmpl import TransTmpl
from hwt.hdlObjects.types.bits import Bits
from hwt.hdlObjects.types.hdlType import HdlType
from hwt.hdlObjects.types.struct import HStruct, HStructField
from hwt.hdlObjects.types.union import HUnion
from hwt.interfaces.std import Handshaked, Signal, VldSynced
from hwt.interfaces.structIntf import StructIntf
from hwt.interfaces.unionIntf import UnionSource, UnionSink
from hwt.interfaces.utils import addClkRstn
from hwt.synthesizer.byteOrder import reverseByteOrder
from hwt.synthesizer.param import Param
from hwt.synthesizer.rtlLevel.rtlSignal import RtlSignal
from hwtLib.amba.axis_comp.base import AxiSCompBase
from hwtLib.amba.axis_comp.templateBasedUnit import TemplateBasedUnit
from hwtLib.handshaked.builder import HsBuilder
from hwtLib.handshaked.streamNode import ExclusiveStreamGroups, StreamNode


class AxiS_frameParser(AxiSCompBase, TemplateBasedUnit):
    """
    Parse frame specified by HStruct into fields

    .. aafig::
                                     +---------+
                              +------> field0  |
                              |      +---------+
                      +-------+-+
         input stream |         |    +---------+
        +-------------> parser  +----> field1  |
                      |         |    +---------+
                      +-------+-+
                              |      +---------+
                              +------> field2  |
                                     +---------+

    :note: names in the picture are just illustrative
    """
    def __init__(self, axiSCls,
                 structT: HdlType,
                 tmpl: Optional[TransTmpl]=None,
                 frames: Optional[List[FrameTmpl]]=None):
        """
        :param axiSCls: class of input axi stream interface
        :param structT: instance of HStruct which specifies data format to download
        :param tmpl: instance of TransTmpl for this structT
        :param frames: list of FrameTmpl instances for this tmpl
        :note: if tmpl and frames are None they are resolved from structT parseTemplate
        :note: this unit can parse sequence of frames, if they are specified by "frames"
        :attention: structT can not contain fields with variable size like HStream
        """
        self._structT = structT

        if tmpl is not None:
            assert frames is not None, "tmpl and frames can be used only together"
        else:
            assert frames is None, "tmpl and frames can be used only together"

        self._tmpl = tmpl
        self._frames = frames
        AxiSCompBase.__init__(self, axiSCls)

    def _config(self):
        self.intfCls._config(self)
        # if this is true field interfaces will be of type VldSynced
        # and single ready signal will be used for all
        # else every interface will be instance of Handshaked and it will
        # have it's own ready(rd) signal
        self.SHARED_READY = Param(False)
        # synchronize by last from input axi stream
        # or use internal counter for synchronization
        self.SYNCHRONIZE_BY_LAST = Param(True)

    def _mkFieldIntf(self, parent: Union[StructIntf, UnionSource],
                     structField: HStructField):
        t = structField.dtype
        if isinstance(t, HUnion):
            return UnionSource(t, parent._instantiateFieldFn)
        elif isinstance(t, HStruct):
            return StructIntf(t, parent._instantiateFieldFn)
        else:
            if self.SHARED_READY:
                i = VldSynced()
            else:
                i = Handshaked()
            i.DATA_WIDTH.set(structField.dtype.bit_length())
            return i

    def _declr(self):
        addClkRstn(self)

        if isinstance(self._structT, HStruct):
            intfCls = StructIntf
        elif isinstance(self._structT, HUnion):
            intfCls = UnionSource
        else:
            raise TypeError(self._structT)

        self.dataOut = intfCls(self._structT, self._mkFieldIntf)

        with self._paramsShared():
            self.dataIn = self.intfCls()
            if self.SHARED_READY:
                self.dataOut_ready = Signal()

    def getInDataSignal(self, transPart: TransPart):
        busDataSignal = self.dataIn.data
        high, low = transPart.getBusWordBitRange()
        return busDataSignal[high:low]

    def choiceIsSelected(self, interfaceOfChoice: Union[UnionSource, UnionSink]):
        """
        Check if union member is selected by _select interface in union interface
        """
        parent = interfaceOfChoice._parent
        try:
            r = self._tmpRegsForSelect[parent]
        except KeyError:
            r = HsBuilder(self, parent._select).buff().end
            self._tmpRegsForSelect[parent] = r

        i = parent._interfaces.index(interfaceOfChoice)
        return r.data._eq(i), r.vld

    def connectParts(self, steamNode: StreamNode, words, wordIndexReg: RtlSignal):
        g = ExclusiveStreamGroups()

        for wIndx, transParts, _ in words:
            # each word index is used and there may be TransParts which are
            # representation of padding
            wordStreamNode = StreamNode()
            isThisWord = wordIndexReg._eq(wIndx)
            for part in transParts:
                self.connectPart(wordStreamNode, part, isThisWord, True)

            g.append((isThisWord, wordStreamNode))

        steamNode.slaves.append(g)

    def connectPart(self,
                    wordStreamNode: StreamNode,
                    part: Union[TransPart, ChoicesOfFrameParts],
                    isThisWord: RtlSignal,
                    en: Union[RtlSignal, bool]):

        busVld = self.dataIn.valid
        tToIntf = self.dataOut._fieldsToInterfaces

        if isinstance(part, ChoicesOfFrameParts):
            # for unions
            groupOfChoices = ExclusiveStreamGroups()

            for choice in part:
                # connect data signals of choices and collect info about streams
                intfOfChoice = tToIntf[choice.tmpl.origin]
                isSelected, isSelectValid = self.choiceIsSelected(intfOfChoice)
                _en = isSelectValid & isSelected & en
                streamNodeOfChoice = StreamNode()

                for p in choice:
                    self.connectPart(streamNodeOfChoice, p, isThisWord, _en)

                groupOfChoices.append((isSelectValid & isSelected, streamNodeOfChoice))

            if part.isLastPart():
                # synchronization of reading from _select register for unions
                parentIntf = tToIntf[part.origin.parent.origin]
                sel = self._tmpRegsForSelect[parentIntf]
                wordStreamNode.masters.append(sel)

            wordStreamNode.slaves.append(groupOfChoices)
            return

        if part.isPadding:
            return

        fPartSig = self.getInDataSignal(part)
        fieldInfo = part.tmpl.origin

        try:
            signalsOfParts = self._signalsOfParts[part.tmpl]
        except KeyError:
            signalsOfParts = []
            self._signalsOfParts[part.tmpl] = signalsOfParts

        if part.isLastPart():
            # connect all parts in this group to output stream
            signalsOfParts.append(fPartSig)
            intf = self.dataOut._fieldsToInterfaces[fieldInfo]
            intf.data ** self.byteOrderCare(
                                       Concat(
                                              *reversed(signalsOfParts)
                                             )
                                      )
            wordStreamNode.slaves.append(intf)
            signalsOfParts = []
        else:
            dataVld = busVld & isThisWord & en
            # part is in some word as last part, we have to store its value to register
            # until the last part arrive
            fPartReg = self._reg("%s_part_%d" % (fieldInfo.name,
                                                 len(signalsOfParts)),
                                 fPartSig._dtype)
            If(dataVld,
               fPartReg ** fPartSig
            )
            signalsOfParts.append(fPartReg)

    def _impl(self):
        r = self.dataIn
        self.parseTemplate()
        words = list(self.chainFrameWords())
        assert not (self.SYNCHRONIZE_BY_LAST and len(self._frames) > 1)
        maxWordIndex = words[-1][0]
        wordIndex = self._reg("wordIndex", Bits(log2ceil(maxWordIndex + 1)), 0)
        busVld = r.valid

        if self.IS_BIGENDIAN:
            byteOrderCare = reverseByteOrder
        else:
            def byteOrderCare(sig):
                return sig

        self.byteOrderCare = byteOrderCare
        self._tmpRegsForSelect = {}
        self._signalsOfParts = {}

        mainStreamNode = StreamNode()
        self.connectParts(mainStreamNode, words, wordIndex)

        if self.SHARED_READY:
            busReady = self.dataOut_ready
            r.ready ** busReady
        else:
            busReady = mainStreamNode.ack()
            mainStreamNode.sync(busVld)

        r.ready ** busReady

        if self.SYNCHRONIZE_BY_LAST:
            last = r.last
        else:
            last = wordIndex._eq(maxWordIndex)

        If(busVld & busReady,
            If(last,
               wordIndex ** 0
            ).Else(
                wordIndex ** (wordIndex + 1)
            )
        )


if __name__ == "__main__":
    from hwtLib.types.ctypes import uint16_t, uint32_t, uint64_t
    from hwt.synthesizer.shortcuts import toRtl
    from hwtLib.amba.axis import AxiStream

    t = HStruct(
      (uint64_t, "item0"),  # tuples (type, name) where type has to be instance of Bits type
      (uint64_t, None),  # name = None means this field will be ignored
      (uint64_t, "item1"),
      (uint64_t, None),
      (uint16_t, "item2"),
      (uint16_t, "item3"),
      (uint32_t, "item4"),
      (uint32_t, None),
      (uint64_t, "item5"),  # this word is split on two bus words
      (uint32_t, None),
      (uint64_t, None),
      (uint64_t, None),
      (uint64_t, None),
      (uint64_t, "item6"),
      (uint64_t, "item7"),
      (HStruct(
          (uint64_t, "item0"),
          (uint64_t, "item1"),
       ),
       "struct0")
      )
    u = AxiS_frameParser(AxiStream, t)
    u.DATA_WIDTH.set(32)
    print(toRtl(u))
