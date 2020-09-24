from math import ceil

from hwt.code import Concat, log2ceil
from hwt.hdl.typeShortcuts import vec
from hwtLib.amba.axi_comp.lsu.interfaces import AddrDataIntf
from hwtLib.mem.cam import Cam


def expand_byte_mask_to_bit_mask(m):
    res = []
    for b in m:
        B = []
        for _ in range(8):
            B.append(b)

        res.append(Concat(*B))
    return Concat(*reversed(res))


def apply_write_with_mask(current_data, new_data, write_mask):
    return (
        (current_data & ~expand_byte_mask_to_bit_mask(write_mask)) | 
        (new_data & expand_byte_mask_to_bit_mask(write_mask))
    )


class CamWithReadPort(Cam):
    """
    Content addressable memory with a read port which can be used
    to read cam array by index
    """

    def _declr(self):
        Cam._declr(self)
        r = self.read = AddrDataIntf()
        r.ADDR_WIDTH = log2ceil(self.ITEMS - 1)
        r.DATA_WIDTH = self.KEY_WIDTH

    def _impl(self):
        Cam._impl(self)
        self.read.data(self._mem[self.read.addr])


def extend_to_width_multiple_of_8(sig):
    """
    make width of signal modulo 8 equal to 0
    """
    w = sig._dtype.bit_length()
    cosest_multiple_of_8 = ceil((w // 8) / 8) * 8
    if cosest_multiple_of_8 == w:
        return sig
    else:
        return Concat(vec(0, cosest_multiple_of_8 - w), sig)
