from hwt.code import log2ceil
from hwt.hdlObjects.constants import INTF_DIRECTION
from hwt.hdlObjects.transTmpl import TransTmpl
from hwt.hdlObjects.typeShortcuts import vecT
from hwt.hdlObjects.types.array import Array
from hwt.hdlObjects.types.bits import Bits
from hwt.hdlObjects.types.hdlType import HdlType
from hwt.hdlObjects.types.struct import HStruct
from hwt.hdlObjects.types.structUtils import BusFieldInfo
from hwt.interfaces.std import BramPort_withoutClk, RegCntrl, Signal, VldSynced
from hwt.interfaces.structIntf import StructIntf
from hwt.interfaces.utils import addClkRstn
from hwt.synthesizer.interfaceLevel.mainBases import InterfaceBase
from hwt.synthesizer.interfaceLevel.unit import Unit
from hwt.synthesizer.interfaceLevel.unitImplHelpers import getSignalName
from hwt.synthesizer.param import evalParam
from hwt.synthesizer.rtlLevel.mainBases import RtlSignalBase


class BusEndpoint(Unit):
    """
    Abstract unit
    Delegate request from bus to fields of structure
    write has higher priority
    
    .. aafig::
        +------+    +----------+     +---------+
        | bus  +---->          +-----> field0  |
        |      <----+          <-----+         |
        +------+    |          |     +---------+
                    |          |
                    | endpoint |     +---------+
                    |          +-----> field1  |
                    |          <-----+         |
                    |          |     +---------+
                    |          |
                    |          |     +---------+
                    |          +-----> field2  |
                    |          <-----+         |
                    +----------+     +---------+

    
    
    """
    def __init__(self, structTemplate, offset=0, intfCls=None):
        """
        :param structTemplate:
            interface types for field type:
                primitive types like Bits -> RegCntrl interface
                Array -> BramPort_withoutClk interface
        """
        assert intfCls is not None, "intfCls has to be specified"
        self._intfCls = intfCls
        self.STRUCT_TEMPLATE = structTemplate
        self.OFFSET = offset
        Unit.__init__(self)

    def _getWordAddrStep(self):
        raise NotImplementedError("Should be overridden in concrete implementation, this is abstract class")

    def _getAddrStep(self):
        raise NotImplementedError("Should be overridden in concrete implementation, this is abstract class")

    def _config(self):
        self._intfCls._config(self)

    def _declr(self):
        addClkRstn(self)

        with self._paramsShared():
            self.bus = self._intfCls()

        self.decoded = StructIntf(self.STRUCT_TEMPLATE, instantiateFieldFn=self._mkFieldInterface)

    def getPort(self, transTmpl):
        return self.decoded._fieldsToInterfaces[transTmpl.origin]

    def isInMyAddrRange(self, addrSig):
        return (addrSig >= self._getMinAddr()) & (addrSig < self._getMaxAddr())

    def _parseTemplate(self):
        self._directlyMapped = []
        self._bramPortMapped = []
        self.ADRESS_MAP = []

        self.WORD_ADDR_STEP = self._getWordAddrStep()
        self.ADDR_STEP = self._getAddrStep()

        AW = evalParam(self.ADDR_WIDTH).val
        SUGGESTED_AW = self._suggestedAddrWidth()
        assert SUGGESTED_AW <= AW, (SUGGESTED_AW, AW)
        tmpl = TransTmpl(self.STRUCT_TEMPLATE, bitAddr=self.OFFSET)
        fieldTrans = tmpl.walkFlatten(shouldEnterFn=lambda tmpl: not isinstance(tmpl.dtype, Array))
        for (_, transactionTmpl) in fieldTrans:
            intf = self.getPort(transactionTmpl)

            if isinstance(intf, RegCntrl):
                self._directlyMapped.append(transactionTmpl)
            elif isinstance(intf, BramPort_withoutClk):
                self._bramPortMapped.append(transactionTmpl)
            else:
                raise NotImplementedError(intf)
            self.ADRESS_MAP.append(transactionTmpl)

    def _getMaxAddr(self):
        lastItem = self.ADRESS_MAP[-1]
        return lastItem.bitAddrEnd // self._getAddrStep()

    def _getMinAddr(self):
        return self.ADRESS_MAP[0].bitAddr // self._getAddrStep()

    def _suggestedAddrWidth(self):
        """
        Based on strut template and offset given resolve how many bits for
        address is needed
        """
        bitSize = self.STRUCT_TEMPLATE.bit_length()
        wordAddrStep = self._getWordAddrStep()
        addrStep = self._getAddrStep()

        maxAddr = (self.OFFSET + bitSize // addrStep)

        # align to word size
        if maxAddr % wordAddrStep != 0:
            wordAddrStep += wordAddrStep - (maxAddr % wordAddrStep)

        return maxAddr.bit_length()

    def propagateAddr(self, srcAddrSig, srcAddrStep, dstAddrSig, dstAddrStep, transTmpl):
        """
        :param srcAddrSig: input signal with address
        :param srcAddrStep: how many bits is addressing one unit of srcAddrSig
        :param dstAddrSig: output signal for address
        :param dstAddrStep: how many bits is addressing one unit of dstAddrSig
        :param transTmpl: TransTmpl which has metainformations about this address space transition
        """
        IN_ADDR_WIDTH = srcAddrSig._dtype.bit_length()

        # _prefix = transTmpl.getMyAddrPrefix(srcAddrStep)
        assert dstAddrStep % srcAddrStep == 0
        if not isinstance(transTmpl.dtype, Array):
            raise TypeError()
        assert transTmpl.bitAddr % dstAddrStep == 0, "Has to be addressable by address with this step"

        addrIsAligned = transTmpl.bitAddr % transTmpl.bit_length() == 0
        bitsForAlignment = ((dstAddrStep // srcAddrStep) - 1).bit_length()
        bitsOfSubAddr = ((transTmpl.bitAddrEnd - transTmpl.bitAddr - 1) // dstAddrStep).bit_length()

        if addrIsAligned:
            bitsOfPrefix = IN_ADDR_WIDTH - bitsOfSubAddr - bitsForAlignment
            prefix = (transTmpl.bitAddr // srcAddrStep) >> (bitsForAlignment + bitsOfSubAddr)
            addrIsInRange = srcAddrSig[IN_ADDR_WIDTH:(IN_ADDR_WIDTH - bitsOfPrefix)]._eq(prefix)
            addr_tmp = srcAddrSig
        else:
            _addr = transTmpl.bitAddr // srcAddrStep
            _addrEnd = transTmpl.bitAddrEnd // srcAddrStep
            addrIsInRange = inRange(srcAddrSig, _addr, _addrEnd)
            addr_tmp = self._sig(dstAddrSig._name + "_addr_tmp", vecT(self.ADDR_WIDTH))
            addr_tmp ** (srcAddrSig - _addr)

        connectedAddr = (dstAddrSig ** addr_tmp[(bitsOfSubAddr + bitsForAlignment):(bitsForAlignment)])

        return (addrIsInRange, connectedAddr)

    def _mkFieldInterface(self, field):
        t = field.dtype
        DW = evalParam(self.DATA_WIDTH).val

        if isinstance(t, Bits):
            p = RegCntrl()
            dw = t.bit_length()
        elif isinstance(t, Array):
            p = BramPort_withoutClk()
            dw = t.elmType.bit_length()
            p.ADDR_WIDTH.set(log2ceil(evalParam(t.size).val - 1))
        else:
            raise NotImplementedError(t)

        if dw == DW:
            # use param instead of value to improve readability
            dw = self.DATA_WIDTH
            p._replaceParam("DATA_WIDTH", dw)
        else:
            p.DATA_WIDTH.set(dw)

        return p

    @classmethod
    def _resolveRegStructFromIntfMap(cls, prefix, interfaceMap, DATA_WIDTH, aliginFields=False):
        """
        Generate flatened register map for HStruct

        :param prefix: prefix for register name
        :param interfaceMap: iterable of
            tuple (type, name) or
            interface or
            tuple (list of interface, prefix, [aliginFields])
            (aliginFields is optional flag if set all items from list will be aligned to bus word size, default is false)
        :param DATA_WIDTH: width of word
        :return: generator of tuple (type, name, BusFieldInfo)
        """
        for m in interfaceMap:
            if isinstance(m, (InterfaceBase, RtlSignalBase)):
                intf = m
                name = getSignalName(intf)
                if isinstance(intf, (RtlSignalBase, Signal)):
                    dtype = intf._dtype
                    access = "r"
                elif isinstance(intf, VldSynced):
                    # assert intf._direction == INTF_DIRECTION.SLAVE
                    dtype = intf.data._dtype
                    access = "w"
                elif isinstance(intf, RegCntrl):
                    dtype = intf.din._dtype
                    access = "rw"
                elif isinstance(intf, BramPort_withoutClk):
                    dtype = Array(vecT(evalParam(intf.DATA_WIDTH).val),
                                  2 ** evalParam(intf.ADDR_WIDTH).val)
                    access = "rw"
                else:
                    raise NotImplementedError(intf)
                
                info = BusFieldInfo(access=access, fieldInterface=intf)
                
                if aliginFields:
                    fillUpWidth = DATA_WIDTH - dtype.bit_length()
                    if fillUpWidth > 0:
                        yield (vecT(fillUpWidth), None, None)

                yield (dtype, prefix + name, info)
            else:
                l = len(m)
                if l == 2:
                    typeOrListOfInterfaces, nameOrPrefix = m
                    align = False
                else:
                    typeOrListOfInterfaces, nameOrPrefix, align = m

                if isinstance(typeOrListOfInterfaces, HdlType):
                    # tuple (type, name)
                    yield (typeOrListOfInterfaces, prefix + nameOrPrefix, None)
                    if align:
                        fillUpWidth = DATA_WIDTH - typeOrListOfInterfaces.bit_length()
                        if fillUpWidth > 0:
                            yield (vecT(fillUpWidth), None, None)
                else:
                    # tuple (list of interfaces, prefix)
                    yield from cls._resolveRegStructFromIntfMap(prefix + nameOrPrefix,
                                                                typeOrListOfInterfaces,
                                                                DATA_WIDTH,
                                                                align)

    @classmethod
    def _fromInterfaceMap(cls, parent, onParentName, bus, busDataWidth, configFn, interfaceMap):
        """
        Generate converter by specified struct and connect interfaces if are specified
        in impl phase

        :param parent: unit where converter should be instantiated
        :param onParentName: name of converter in parent
        :param bus: bus interface for converter
        :param configFn: function (converter) which should be used for configuring of converter
        :param interfaceMap: iterable of tuple (type, name) or interface
            or tuple (list of interface, prefix, optionally align)
            (align is optional flag if set all items from list will be aligned (little-endian)
            to bus word size, default is false)
            if interface is specified it will be automatically connected
        """

        regsFlatten = []
        intfMap = {}
        DATA_WIDTH = evalParam(bus.DATA_WIDTH).val
        # build flatten register map
        for typ, name, info in cls._resolveRegStructFromIntfMap("", interfaceMap, DATA_WIDTH):
            if info is not None:
                regsFlatten.append((typ, name, info))
                intfMap[name] = info.fieldInterface
            else:
                regsFlatten.append((typ, name))

        # instantiate converter
        conv = cls(HStruct(*regsFlatten))
        configFn(conv)

        setattr(parent, onParentName, conv)

        conv.bus ** bus

        # connect interfaces as was specified by register map
        for regName, intf in intfMap.items():
            convIntf = getattr(conv.decoded, regName)

            if isinstance(intf, Signal):
                assert intf._direction == INTF_DIRECTION.MASTER
                convIntf.din ** intf

            elif isinstance(intf, RtlSignalBase):
                convIntf.din ** intf

            elif isinstance(intf, RegCntrl):
                assert intf._direction == INTF_DIRECTION.SLAVE
                intf ** convIntf

            elif isinstance(intf, VldSynced):
                assert intf._direction == INTF_DIRECTION.SLAVE
                convIntf.dout ** intf

            elif isinstance(intf, BramPort_withoutClk):
                intf ** convIntf
            else:
                raise NotImplementedError(intf)