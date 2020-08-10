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

def test_p_invert_after_cq_passthrough(nvme0):
    """
    The value of the Phase Tag is inverted each pass through the Complete Queue.
    """
    # cqid: 1, PC, depth: 2
    cq = IOCQ(nvme0, 1, 2, PRP())
    # create four SQ, both use the same CQ
    sq3 = IOSQ(nvme0, 3, 16, PRP(), cqid=1)
    sq5 = IOSQ(nvme0, 5,16, PRP(), cqid=1)
    sq2 = IOSQ(nvme0, 2, 16, PRP(), cqid=1)
    sq4 = IOSQ(nvme0, 4,16, PRP(), cqid=1)
    # IO command templates: opcode and namespace
    write_cmd = SQE(1, 1)
    read_cmd = SQE(2, 1)

    for i in range(2):
        logging.info("before cqe {} ,value {}".format(i,CQE(cq[i%2]).p))

    # write in sq3, lba1-lba2, 1 page, aligned
    w1 = SQE(*write_cmd)
    write_buf = PRP(ptype=32, pvalue=0xaaaaaaaa)
    w1.prp1 = write_buf
    w1[10] = 1
    w1[12] = 1 # 0based
    w1.cid = 0x123
    sq3[0] = w1
    sq3.tail = 1

    # add some delay, so ssd should finish w1 before w2
    time.sleep(0.1)

    # write in sq5, lba5-lba16, 2 page, non aligned
    w2 = SQE(*write_cmd)
    buf1 = PRP(ptype=32, pvalue=0xbbbbbbbb)
    buf1.offset = 2048
    w2.prp1 = buf1
    w2.prp2 = PRP(ptype=32, pvalue=0xcccccccc)
    w2[10] = 5
    w2[12] = 11 # 0based
    w2.cid = 0x567
    sq5[0] = w2
    sq5.tail = 1

    # cqe for w1
    while CQE(cq[0]).p == 0: pass
    cqe = CQE(cq[0])
    assert cqe.cid == 0x123
    assert cqe.sqid == 3
    assert cqe.sqhd == 1
    cq.head = 1

    # cqe for w2
    while CQE(cq[1]).p == 0: pass
    cqe = CQE(cq[1])
    assert cqe.cid == 0x567
    assert cqe.sqid == 5
    assert cqe.sqhd == 1

    cq.head = 2

    for i in range(2):
        logging.info("after cqe {} ,value {}".format(i,CQE(cq[i%2]).p))

    for i in range(2):
        logging.info("before cqe {} ,value {}".format(i,CQE(cq[i%2]).p))

    # write in sq3, lba1-lba2, 1 page, aligned
    w3 = SQE(*write_cmd)
    write_buf = PRP(ptype=32, pvalue=0xdddddddd)
    w3.prp1 = write_buf
    w3[10] = 1
    w3[12] = 1 # 0based
    w3.cid = 0x147
    sq2[0] = w3
    sq2.tail = 1

    # add some delay, so ssd should finish w1 before w2
    time.sleep(0.1)

    # write in sq5, lba5-lba16, 2 page, non aligned
    w4 = SQE(*write_cmd)
    buf1 = PRP(ptype=32, pvalue=0xeeeeeeee)
    buf1.offset = 2048
    w4.prp1 = buf1
    w4.prp2 = PRP(ptype=32, pvalue=0xffffffff)
    w4[10] = 5
    w4[12] = 11 # 0based
    w4.cid = 0x167
    sq4[0] = w4
    sq4.tail = 1

    # cqe for w3
    while CQE(cq[0]).p == 1: pass
    cqe = CQE(cq[0])
    assert cqe.cid == 0x147
    assert cqe.sqid == 2
    assert cqe.sqhd == 1
    cq.head = 1
    # cqe for w4
    while CQE(cq[1]).p == 1: pass
    cqe = CQE(cq[1])
    assert cqe.cid == 0x167
    assert cqe.sqid == 4
    assert cqe.sqhd == 1
    cq.head = 2
    time.sleep(1)
    for i in range(2):
        logging.info("after cqe {} ,value {}".format(i,CQE(cq[i%2]).p))

