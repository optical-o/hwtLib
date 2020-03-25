from hwt.hdl.types.bits import Bits
from hwt.synthesizer.hObjList import HObjList
from hwt.synthesizer.interfaceLevel.unitImplHelpers import getClk, getRst,\
    getSignalName


class AbstractComponentBuilder(object):
    """
    Helper class which simplifies instanciation of commonly used components
    with configuration based on input/output interface

    :ivar compId: used for sequential number of components
    :ivar lastComp: last builded component
    :ivar end: last interface of data-path

    :attention: input port is taken from self.end
    """

    def __init__(self, parent, srcInterface, name=None):
        """
        :param parent: unit in which will be all units created by this builder instantiated
        :param name: prefix for all instantiated units
        :param srcInterface: start of data-path
        """
        self.parent = parent
        self.lastComp = None
        self.end = srcInterface
        if name is None:
            name = "gen_" + getSignalName(srcInterface)

        self.name = name
        self.compId = 0

    def getClk(self):
        """
        lookup clock signal on parent
        """
        end = self.end
        if end is None:
            return getClk(self.parent)
        else:
            return end._getAssociatedClk()

    def getRstn(self):
        """
        lookup reset(n) signal on parent
        """
        end = self.end
        if end is None:
            rst = getRst(self.parent)
        else:
            rst = end._getAssociatedRst()

        if isinstance(rst._dtype, Bits) and rst._dtype.negated:
            return rst
        else:
            return ~rst

    def getInfCls(self):
        """
        Get class of interface which this builder is currently using.
        """
        return self._getIntfCls(self.end)

    def _getIntfCls(self, intf):
        """
        Get real interface class of interface
        """
        if isinstance(intf, HObjList):
            return self._getIntfCls(intf[0])

        return intf.__class__

    def _findSuitableName(self, unitName):
        """
        find suitable name for component (= name without collisions)
        """
        while True:
            name = "%s_%s_%d" % (self.name, unitName, self.compId)
            try:
                getattr(self.parent, name)
            except AttributeError:
                return name
                break
            self.compId += 1

        self.compId += 1

    def _propagateClkRstn(self, u):
        """
        Connect clock and reset to unit "u"
        """
        if hasattr(u, "clk"):
            u.clk(self.getClk())

        if hasattr(u, 'rst_n'):
            u.rst_n(self.getRstn())

        if hasattr(u, "rst"):
            u.rst(~self.getRstn())