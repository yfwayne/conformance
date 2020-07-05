# Copyright (C) 2020 Crane Chu <cranechu@gmail.com>
# This file is part of pynvme's conformance test
#
# pynvme's conformance test is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# pynvme's conformance test is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pynvme's conformance test. If not, see
# <http://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-


import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_cq_p_phase_bit(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)

    # send commands
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1
    sq[1] = SQE(3<<16+0, 1); sq.tail = 0
    sq[0] = SQE(2<<16+0, 1); sq.tail = 1
    sq[1] = SQE(1<<16+0, 1); sq.tail = 0

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[1][3] == 0x10003
    assert cq[2][3] == 0
    cq.head = 1
    time.sleep(0.1)
    assert cq[2][3] == 0x10002
    assert cq[0][3] == 0x10004
    cq.head = 2
    time.sleep(0.1)
    # p-bit changed to 0
    assert cq[0][3] == 0x00001


def test_cq_sqhd(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)

    # send commands
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1; time.sleep(0.1)
    sq[1] = SQE(3<<16+0, 1); sq.tail = 0; time.sleep(0.1)
    sq[0] = SQE(2<<16+0, 1); sq.tail = 1; time.sleep(0.1)
    sq[1] = SQE(1<<16+0, 1); sq.tail = 0; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    assert cq[0][2] == 0x10001
    assert cq[1][2] == 0x10000
    assert cq[2][2] == 0
    cq.head = 1
    time.sleep(0.1)
    assert cq[2][2] == 0x10001
    assert cq[0][2] == 0x10001
    cq.head = 2
    time.sleep(0.1)
    assert cq[0][2] == 0x10000
    assert cq[0][0] == 0
    assert cq[0][1] == 0
    
