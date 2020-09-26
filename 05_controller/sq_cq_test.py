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


def test_sq_cq_around(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 5, PRP(), cqid=1)

    # send commands
    sq[0] = SQE(4<<16+0, 1)
    sq[1] = SQE(3<<16+0, 1)
    sq[2] = SQE(2<<16+0, 1)
    sq[3] = SQE(1<<16+0, 1)
    sq.tail = 4

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[1][3] == 0x10003
    assert cq[2][3] == 0
    
    cq.head = 1
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[2][3] == 0x10002
    
    cq.head = 2
    time.sleep(0.1)
    assert cq[2][3] == 0x10002
    assert cq[1][3] == 0x10003
    assert cq[0][3] == 0x00001

    sq.delete()
    cq.delete()


def test_sq_overflow(nvme0):
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


@pytest.mark.parametrize("tail", [0, 2, 3, 0xffff, 0x10000])
def test_sq_doorbell_invalid(nvme0, tail):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = tail

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


@pytest.mark.parametrize("head", [0, 2, 3, 0xffff, 0x10000])
def test_cq_doorbell_invalid(nvme0, head):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = 1

    time.sleep(0.1)
    cq.head = head
    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
        nvme0.getfeatures(7).waitdone()
    sq.delete()
    cq.delete()

    
def test_sq_cq_another_sq(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())

    # send commands in sq1
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)
    sq[0] = SQE(4<<16+0, 1)
    sq[1] = SQE(3<<16+0, 1)
    sq.tail = 2

    sq2 = IOSQ(nvme0, 2, 3, PRP(), cqid=1)
    sq2[0] = SQE(2<<16+0, 1)
    sq2[1] = SQE(1<<16+0, 1)
    sq2.tail = 2

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
    assert cq[0][3] == 0x00001

    sq.delete()
    sq2.delete()
    cq.delete()


def _test_cq_sqhd_aer(nvme0,buf):
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


