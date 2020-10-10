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
import nvme as d

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_create_cq_with_invalid_prp_offset(nvme0):
    prp = PRP(4096)
    #Spec NVM-Express-1_4-2019.06.10-Ratified
    #Figure 149: In both cases the PRP Entry shall have an offset of 0h.
    prp.offset = 0
    IOCQ(nvme0, 1, 10, prp).delete()

    #ERROR status: 00/13:invalid prp offset
    prp.offset = 2048
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOCQ(nvme0, 1, 10, prp).delete()

    prp.offset = 2050
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOCQ(nvme0, 1, 10, prp).delete()

    prp.offset = 4095
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOCQ(nvme0, 2, 10, prp).delete()

    prp.offset = 255
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOCQ(nvme0, 2, 10, prp).delete()


def test_create_sq_with_invalid_prp_offset(nvme0):
    prp = PRP(4096)
    cq = IOCQ(nvme0, 1, 10, prp)

    #Spec NVM-Express-1_4-2019.06.10-Ratified
    #Figure 153: In both cases, the PRP Entry shall have an offset of 0h.
    prp.offset = 0
    IOSQ(nvme0, 1, 10, prp, cqid=1).delete()

    prp.offset = 2048
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOSQ(nvme0, 1, 10, prp, cqid=1).delete()

    prp.offset = 2050
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOSQ(nvme0, 1, 10, prp, cqid=1).delete()

    prp.offset = 4095
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOSQ(nvme0, 2, 10, prp, cqid=1).delete()

    prp.offset = 255
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOSQ(nvme0, 2, 10, prp, cqid=1).delete()

    cq.delete()


@pytest.mark.parametrize("repeat", range(2))
def test_hello_world(nvme0, nvme0n1, repeat):
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'
    qpair = Qpair(nvme0, 16)  # create IO SQ/CQ pair, with 16 queue-depth

    # send write and read command
    def write_cb(cdw0, status1):  # command callback function
        nvme0n1.read(qpair, read_buf, 0, 1)
        assert status1 == 1  # phase-bit
    nvme0n1.write(qpair, write_buf, 0, 1, cb=write_cb)

    # wait commands complete and verify data
    assert read_buf[10:21] != b'hello world'
    qpair.waitdone(2)
    assert read_buf[10:21] == b'hello world'


def test_format_512(nvme0n1):
    nvme0n1.format(512)


@pytest.mark.parametrize("mdts", [64, 128, 256, 512, 800, 1024, 16*1024, 32*1024, 32*1024+64, 32*1024+64+8,64*1024])
def test_write_mdts(nvme0, mdts):
    cq = IOCQ(nvme0, 1, 2, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)

    # prp for the long buffer
    write_buf_1 = PRP(ptype=32, pvalue=0xaaaaaaaa)
    pages = mdts//8
    pages -= 1

    prp_list = PRPList()
    prp_list_head = prp_list
    while pages:
        for i in range(511):
            if pages:
                prp_list[i] = PRP()
                pages -= 1
                logging.debug(pages)
        if pages>1:
            tmp = PRPList()
            prp_list[511] = tmp
            prp_list = tmp
            logging.debug("prp_list")
        elif pages==1:
            prp_list[511] = PRP()
            pages -= 1
            logging.debug(pages)

    w1 = SQE(1, 1)
    w1.prp1 = write_buf_1
    w1.prp2 = prp_list_head
    w1[12] = mdts-1 # 0based, nlba
    w1.cid = 0x123
    sq[0] = w1
    sq.tail = 1

    time.sleep(1)
    cqe = CQE(cq[0])
    logging.info(cqe)
    assert cqe.p == 1
    assert cqe.cid == 0x123
    assert cqe.sqhd == 1
    logging.info("cqe status is {}".format(cqe.status))
    assert cqe.status == 0 or cqe.status == 2
    cq.head = 1

    sq.delete()
    cq.delete()


@pytest.mark.parametrize("offset", [0, 4, 16, 32, 512, 800, 1024, 3000])
def test_page_offset(nvme0, nvme0n1, qpair, buf, offset):
    # fill the data
    write_buf = Buffer(512)
    nvme0n1.write(qpair, write_buf, 0x5aa5).waitdone()

    # read the data to different offset and check lba
    buf.offset = offset
    nvme0n1.read(qpair, buf, 0x5aa5).waitdone()
    assert buf[offset] == 0xa5
    assert buf[offset+1] == 0x5a


@pytest.mark.parametrize("offset", [1, 2, 3, 501, 502])
def test_page_offset_invalid(nvme0, nvme0n1, qpair, offset):
    # fill the data
    write_buf = Buffer(512)
    nvme0n1.write(qpair, write_buf, 0xa5).waitdone()

    # read the data to different offset and check lba
    buf = Buffer(1024, ptype=0, pvalue=1)
    buf.offset = offset

    # Spec NVM-Express-1_4-2019.06.10-Ratified
    # Figure 108:Note: The controller is not required to check that bits 1:0
    # are cleared to 00b. The controller may report an error of PRP Offset Invalid
    # pytest warning may not appear here
    nvme0n1.read(qpair, buf, 0xa5).waitdone()
    assert buf[offset] != 0xa5


@pytest.mark.parametrize("offset", [4, 16, 32, 512, 800, 1024, 3000])
def test_admin_page_offset(nvme0, offset):
    buf = d.Buffer(4096*2, 'controller identify data')
    buf.offset = offset
    assert buf[offset] == 0
    nvme0.identify(buf).waitdone()
    logging.info(buf.dump(32))
    assert buf[0] == 0
    assert buf[offset] != 0


@pytest.mark.parametrize("offset", [1, 2, 3, 501, 502])
def test_admin_page_offset_invalid(nvme0, nvme0n1, qpair, offset):
    buf = d.Buffer(4096*2, 'controller identify data')
    buf.offset = offset
    # pytest warning may not appear here
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        nvme0.identify(buf).waitdone()


def test_valid_offset_prp_in_list(nvme0):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    buf = PRP(ptype=32, pvalue=0xffffffff)
    buf.offset = 0x10

    prp_list = PRPList()
    prp_list.offset = 0x20

    for i in range(8):
        tmp = PRP(ptype=32, pvalue=0xffffffff)
        prp_list[i] = tmp

    logging.info(prp_list.dump(64))
    print(buf.dump(32))
    for i in range(8):
        print(prp_list[i].dump(32))

    cmd = SQE(2, 1)
    cmd.prp1 = buf
    cmd.prp2 = prp_list
    cmd[12] = 0x4000001f
    sq[0] = cmd
    logging.info(sq[0])
    sq.tail = 1
    while CQE(cq[0]).p == 0: pass
    cq.head = 1
    logging.info(cq[0])
    logging.info(hex(cq[0][3]>>17))
    print(buf.dump(32))
    for i in range(8):
        print(prp_list[i].dump(32))
    assert (cq[0][3]>>17)&0x3ff == 0x0

    sq.delete()
    cq.delete()


def test_invalid_offset_prp_in_list(nvme0):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    buf = PRP(ptype=32, pvalue=0xffffffff)
    buf.offset = 0x10

    prp_list = PRPList()
    prp_list.offset = 0x20

    for i in range(8):
        tmp = PRP(ptype=32, pvalue=0xffffffff)
        tmp.offset = 0x10
        prp_list[i] = tmp

    logging.info(prp_list.dump(64))
    print(buf.dump(32))
    for i in range(8):
        print(prp_list[i].dump(32))

    cmd = SQE(2, 1)
    cmd.prp1 = buf
    cmd.prp2 = prp_list
    cmd[12] = 0x4000001f
    sq[0] = cmd
    logging.info(sq[0])
    sq.tail = 1
    while CQE(cq[0]).p == 0: pass
    cq.head = 1
    logging.info(cq[0])
    logging.info(hex(cq[0][3]>>17))
    print(buf.dump(32))
    for i in range(8):
        print(prp_list[i].dump(32))
    status = (cq[0][3]>>17)&0x3ff
    assert status == 0x0013 or status == 0

    sq.delete()
    cq.delete()


