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


def test_sq_cq_wrap(nvme0):
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
    assert cq[0][3] == 0x10004
    assert cq[2][3] == 0x10002
    cq.head = 2
    assert cq[2][3] == 0x10002
    assert cq[1][3] == 0x10003
    assert cq[0][3] == 0x00001

    sq.delete()
    cq.delete()


def test_sq_wrap_overflow(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)

    # send commands
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1
    sq[1] = SQE(3<<16+0, 1); sq.tail = 0
    sq[0] = SQE(2<<16+0, 1); sq.tail = 0
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.getfeatures(7).waitdone()

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[1][3] == 0x10003
    assert cq[2][3] == 0

    time.sleep(1)
    assert cq[2][3] == 0
    assert cq[3][3] == 0
    assert cq[4][3] == 0
    logging.info(sq[0])
    logging.info(cq[0])

    sq.delete()
    cq.delete()


def test_delete_cq_before_sq(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    with pytest.warns(UserWarning, match="ERROR status: 01/0c"):
        cq.delete()


def test_sq_doorbell(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = 1

    time.sleep(0.1)
    sq.delete()
    cq.delete()


def test_sq_doorbell_invalid1(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = 2

    time.sleep(0.1)
    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.getfeatures(7).waitdone()
    sq.delete()
    cq.delete()


def test_sq_doorbell_invalid2(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = 3

    time.sleep(0.1)
    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.getfeatures(7).waitdone()
    sq.delete()
    cq.delete()


def test_cq_doorbell_valid(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    time.sleep(0.1)
    cq.delete()


@pytest.mark.parametrize("head", range(7))
def test_cq_doorbell_invalid(nvme0, head):
    cq = IOCQ(nvme0, 1, 5, PRP())
    cq.head = 0
    time.sleep(0.1)
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.getfeatures(7).waitdone()
    cq.delete()


def test_sq_cq_another_sq(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())

    # send commands in sq1
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1
    sq[1] = SQE(3<<16+0, 1); sq.tail = 0

    sq2 = IOSQ(nvme0, 2, 2, PRP(), cqid=1)
    sq2[0] = SQE(2<<16+0, 1); sq2.tail = 1
    sq2[1] = SQE(1<<16+0, 1); sq2.tail = 0

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[1][3] == 0x10003
    assert cq[2][3] == 0
    cq.head = 1
    assert cq[2][3] == 0x10002
    assert cq[0][3] == 0x10004
    cq.head = 2
    assert cq[0][3] == 0x00001

    sq.delete()
    sq2.delete()
    cq.delete()


def test_cqe_sqhd_aer(nvme0,buf):
    #Create cq and sq
    a=()
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 5, PRP(), cqid=1)

    #Trigger aer cmd response by invaild doorbell write value
    sq.tail = 5
    time.sleep(0.1)

    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.waitdone()
    sq.delete()
    cq.delete()

    def call_back_cpl(cpl):
        nonlocal a;a=cpl

    #Check normal cmd cqe sqhd value
    nvme0.getlogpage(1, buf,cb=call_back_cpl).waitdone()
    sqhd1=a[2]&0xffff
    logging.info(sqhd1)

    nvme0.aer(cb=call_back_cpl)
    nvme0.getlogpage(1, buf,cb=call_back_cpl).waitdone()
    sqhd2=a[2]&0xffff
    logging.info(sqhd2)
    assert sqhd2==sqhd1+2

    #Trigger aer cmd response by invaild doorbell write value
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 5, PRP(), cqid=1)
    sq.tail = 5
    time.sleep(0.1)

    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.waitdone()
        #verify aer cmd cqe sqhd
        sqhd_aer=a[2]&0xffff
        sqhd_aer=sqhd2+2
        logging.info("aer sqhd is {}".format(sqhd_aer))

    sq.delete()
    cq.delete()

    #verify the following cmd cqe sqhd
    nvme0.getlogpage(1, buf,cb=call_back_cpl).waitdone()
    sqhd3=a[2]&0xffff
    assert sqhd3==sqhd_aer+3
    logging.info(sqhd3)


def test_send_cmd_2sq_1cq(nvme0):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq1 = IOSQ(nvme0, 1, 10, PRP(), cqid=1)
    sq2 = IOSQ(nvme0, 2, 16, PRP(), cqid=1)

    cdw = SQE(4, 0, 0)
    cdw.nsid = 1  # namespace id
    cdw.cid = 222
    sq1[0] = cdw

    sqe = SQE(*cdw)
    assert sqe[1] == 1
    sqe.cid = 111
    sq2[0] = sqe
    sq2.tail = 1
    time.sleep(0.1)
    sq1.tail = 1
    time.sleep(0.1)

    cqe = CQE(cq[0])
    assert cqe.sct == 0
    assert cqe.sc == 0
    assert cqe.sqid == 2
    assert cqe.sqhd == 1
    assert cqe.p == 1
    assert cqe.cid == 111

    cqe = CQE(cq[1])
    assert cqe.sct == 0
    assert cqe.sc == 0
    assert cqe.sqid == 1
    assert cqe.sqhd == 1
    assert cqe.p == 1
    assert cqe.cid == 222

    cq.head = 2

    sq1.delete()
    sq2.delete()
    cq.delete()


def test_psd_write_2sq_1cq_prp_list(nvme0):
    # cqid: 1, PC, depth: 120
    cq = IOCQ(nvme0, 1, 120, PRP(4096))

    # create two SQ, both use the same CQ
    # sqid: 3, depth: 16
    sq3 = IOSQ(nvme0, 3, 16, PRP(), cqid=1)
    # sqid: 5, depth: 100, so need 2 pages of memory
    sq5 = IOSQ(nvme0, 5, 64*64, PRP(4096*64), cqid=1)

    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        sq_invalid = IOSQ(nvme0, 5, 64*1024, PRP(4096*1024), cqid=1)

    # IO command templates: opcode and namespace
    write_cmd = SQE(1, 1)
    read_cmd = SQE(2, 1)

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

    # read in sq3, lba0-lba23, 3 page with PRP list
    r1 = SQE(*read_cmd)
    read_buf = [PRP() for i in range(3)]
    r1.prp1 = read_buf[0]
    prp_list = PRPList()
    prp_list[0] = read_buf[1]
    prp_list[1] = read_buf[2]
    r1.prp2 = prp_list
    r1[10] = 0
    r1[12] = 23 # 0based
    sq3[1] = r1
    sq3.tail = 2

    # verify read data
    while cq[2].p == 0: pass
    cq.head = 3
    assert read_buf[0].data(0xfff, 0xffc) == 0xbbbbbbbb
    assert read_buf[2].data(3, 0) == 0xcccccccc
    assert read_buf[2].data(0x1ff, 0x1fc) == 0xcccccccc

    # delete all sq/cq
    sq3.delete()
    sq5.delete()
    cq.delete()
    
