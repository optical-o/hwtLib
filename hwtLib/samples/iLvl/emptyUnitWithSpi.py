#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from hwt.intfLvl import EmptyUnit
from hwt.synthesizer.shortcuts import toRtl
from hwtLib.tests.statementTrees import StatementTreesTC
from hwtLib.spi.intf import Spi


class EmptyUnitWithSpi(EmptyUnit):
    def _declr(self):
        self.spi = Spi()

expectedVhdl = """
library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

ENTITY EmptyUnitWithSpi IS
    GENERIC (
        SPI_SLAVE_CNT : INTEGER := 1
    );
    PORT (spi_clk : IN STD_LOGIC;
        spi_cs : IN STD_LOGIC_VECTOR(SPI_SLAVE_CNT - 1 DOWNTO 0);
        spi_miso : OUT STD_LOGIC;
        spi_mosi : IN STD_LOGIC
    );
END EmptyUnitWithSpi;

ARCHITECTURE rtl OF EmptyUnitWithSpi IS
BEGIN
    spi_miso <= 'X';
END ARCHITECTURE rtl;
"""

class EmptyUnitWithSpiTC(unittest.TestCase):
    def test_vhdl(self):
        vhdl = toRtl(EmptyUnitWithSpi())
        StatementTreesTC.strStructureCmp(self, expectedVhdl, vhdl)
        


if __name__ == "__main__":
    suite = unittest.TestSuite()
    # suite.addTest(TwoCntrsTC('test_withStops'))
    suite.addTest(unittest.makeSuite(EmptyUnitWithSpiTC))
    runner = unittest.TextTestRunner(verbosity=3)
    runner.run(suite)

    print(toRtl(EmptyUnitWithSpi()))
