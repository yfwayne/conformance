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
    assert cq[2][3] == 0x10002
    assert cq[0][3] == 0x10004
    
    cq.head = 2
    time.sleep(0.1)
    # p-bit changed to 0
    assert cq[0][3] == 0x00001


def test_cq_sqhd(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)

    # send commands, and check cqe
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1; time.sleep(0.1)
    assert cq[0][2] == 0x10001
    assert cq[0][3] == 0x10004
    assert cq[1][2] == 0
    assert cq[2][2] == 0
    
    # send commands, and check cqe
    sq[1] = SQE(3<<16+0, 1); sq.tail = 0; time.sleep(0.1)
    assert cq[0][2] == 0x10001
    assert cq[0][3] == 0x10004
    assert cq[1][2] == 0x10000
    assert cq[1][3] == 0x10003
    assert cq[2][2] == 0

    # send commands, and check cqe
    sq[0] = SQE(2<<16+0, 1); sq.tail = 1; time.sleep(0.1)
    assert cq[0][2] == 0x10001
    assert cq[0][3] == 0x10004
    assert cq[1][2] == 0x10000
    assert cq[1][3] == 0x10003
    assert cq[2][2] == 0

    # free one cqe before get 3rd cqe
    cq.head = 1; time.sleep(0.1)
    assert cq[2][2] == 0x10001
    assert cq[2][3] == 0x10002
    
    # send commands, and check cqe
    sq[1] = SQE(1<<16+0, 1); sq.tail = 0; time.sleep(0.1)
    cq.head = 2; time.sleep(0.1)
    assert cq[0][2] == 0x10000
    assert cq[0][3] == 0x00001
    assert cq[1][2] == 0x10000
    assert cq[1][3] == 0x10003
    assert cq[2][2] == 0x10001
    assert cq[2][3] == 0x10002


def test_p_invert_after_cq_2_pass(nvme0):
    """
    The value of the Phase Tag is inverted each pass filling the Complete Queue.
    """

    # cqid: 1, PC, depth: 2
    cq = IOCQ(nvme0, 1, 2, PRP())

    # create four SQ, both use the same CQ
    sq3 = IOSQ(nvme0, 3, 10, PRP(), cqid=1)

    # IO command templates: opcode and namespace
    write_cmd = SQE(1, 1)

    # write in sq3
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

    # write in sq5
    w1.cid = 0x567
    sq3[1] = w1
    sq3.tail = 2

    logging.info("aaa")
    # cqe for w1
    while CQE(cq[0]).p == 0: pass
    cqe = CQE(cq[0])
    assert cqe.cid == 0x123
    assert cqe.sqid == 3
    assert cqe.sqhd == 1
    cq.head = 1

    # cqe for w2
    logging.info("bbb")
    while CQE(cq[1]).p == 0: pass
    logging.info("ccc")
    cqe = CQE(cq[1])
    assert cqe.cid == 0x567
    assert cqe.sqid == 3
    assert cqe.sqhd == 2
    cq.head = 0

    assert CQE(cq[0]).p == 1
    assert CQE(cq[1]).p == 1

    # write in sq3
    w1.cid = 0x147
    sq3[2] = w1
    sq3.tail = 3

    # add some delay, so ssd should finish w1 before w2
    time.sleep(0.1)

    # write in sq5
    w1.cid = 0x167
    sq3[3] = w1
    sq3.tail = 4

    # cqe for w3
    while CQE(cq[0]).p == 1: pass
    cqe = CQE(cq[0])
    assert cqe.cid == 0x147
    assert cqe.sqid == 3
    assert cqe.sqhd == 3
    cq.head = 1

    # cqe for w4
    while CQE(cq[1]).p == 1: pass
    cqe = CQE(cq[1])
    assert cqe.cid == 0x167
    assert cqe.sqid == 3
    assert cqe.sqhd == 4
    cq.head = 0

    assert CQE(cq[0]).p == 0
    assert CQE(cq[1]).p == 0


def test_sq_cid1(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # send discontinuous cid commands
    sq[0] = SQE(4<<16+0, 1); sq.tail = 1; time.sleep(0.1)
    sq[1] = SQE(1<<16+0, 1); sq.tail = 2; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10004
    assert cq[1][3] == 0x10001
    sq.delete()
    cq.delete()

    
def test_sq_cid2(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # send max/min cid commands
    sq[0] = SQE(0xFFFF<<16+0, 1); 
    sq[1] = SQE(0<<16+0, 1); sq.tail = 2; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x1FFFF
    assert cq[1][3] == 0x10000
    sq.delete()
    cq.delete()

    
def test_cid_conflict(nvme0):
    mdts_lba = nvme0.mdts//512
    cq = IOCQ(nvme0, 1, 20, PRP())
    sq = IOSQ(nvme0, 1, 20, PRP(), cqid=1)

    # prp for the long buffer
    write_buf_1 = PRP(ptype=32, pvalue=0xaaaaaaaa)
    pages = mdts_lba//8
    pages -= 1

    prp_list = PRPList()
    prp_list_head = prp_list
    while pages:
        logging.info(pages)
        for i in range(63):
            if pages:
                prp_list[i] = PRP()
                pages -= 1
                logging.debug(pages)
        if pages>1:
            tmp = PRPList()
            prp_list[63] = tmp
            prp_list = tmp
            logging.debug("prp_list")
        elif pages==1:
            prp_list[63] = PRP()
            pages -= 1
            logging.debug(pages)

    #send first cmd   
    w1 = SQE((1<<16)+1, 1)
    w1.prp1 = write_buf_1
    w1.prp2 = prp_list_head
    w1[12] = mdts_lba-1 # 0based, nlba
    sq[0] = w1
    sq[1] = w1
    logging.info(sq[0])
    logging.info(sq[1])
    assert sq[0][0]>>16 == 1
    assert sq[1][0]>>16 == 1
    sq.tail = 2

    time.sleep(1)
    logging.info(cq[0])
    logging.info(cq[1])
    cqe = CQE(cq[0])
    assert cqe.p == 1
    status = (cqe[3]>>17)&0x3ff
    assert status == 0 or status == 0x0003
    cqe = CQE(cq[1])
    assert cqe.p == 1
    status = (cqe[3]>>17)&0x3ff
    assert status == 0 or status == 0x0003
    cq.head = 2

    sq.delete()
    cq.delete()   

    
def test_sq_reserved(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # Reserved field is non-zero.
    sq[0] = SQE((1<<16) + (7<<10) + 0, 1); sq.tail = 1; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10001
    sq.delete()
    cq.delete()

    
def test_sq_fuse_is_zero(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # FUSE field is zero.
    sq[0] = SQE((1<<16) + (0<<8), 1); sq.tail = 1; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    assert cq[0][3] == 0x10001
    sq.delete()
    cq.delete()

    
def test_sq_fuse_is_reserved(nvme0):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # FUSE field is 0x3(Reserved).
    sq[0] = SQE((1<<16) + (3<<8), 1); sq.tail = 1; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    #sct=0,sc=2(Invalid Field in Command)
    assert cq[0][3]>>17 == 0x0002
    sq.delete()
    cq.delete()

    
@pytest.mark.parametrize("opc_id", [0x3, 0x7, 0x0b, 0x0f, 0x12, 0x13, 0x16, 0x17, 0x1b])
def test_sq_opc_invalid_admin_cmd(nvme0,opc_id):
    #sct=0,sc=1(Invalid Command Opcode)
    with pytest.warns(UserWarning, match="ERROR status: 00/01"):
        nvme0.send_cmd(opc_id).waitdone()

        
@pytest.mark.parametrize("opc_id", [0x03, 0x07, 0x0a, 0x0b, 0x0f, 0x10, 0x12, 0x13, 0x14])
def test_sq_opc_invalid_nvm_cmd(nvme0,opc_id):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # OPC field is invalid.
    sq[0] = SQE((1<<16) + opc_id, 1); sq.tail = 1; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    #sct=0,sc=1(Invalid Command Opcode)
    assert (cq[0][3]>>17)&0x3ff == 0x0001

    sq.delete()
    cq.delete()

@pytest.mark.parametrize("ns_id", [0, 0x10, 0x100, 0x1000, 0xffffffff])
def test_sq_ns_invalid(nvme0,ns_id):
    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)

    # ns field is invalid.
    sq[0] = SQE(2, ns_id); sq.tail = 1; time.sleep(0.1)

    # check cq
    time.sleep(0.1)
    #sct=0,sc=0x0b(Invalid Namespace or Format)
    assert (cq[0][3]>>17)&0x3ff == 0x000b

    sq.delete()
    cq.delete()    
