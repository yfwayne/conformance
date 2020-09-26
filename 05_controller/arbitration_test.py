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


def nvme_init_wrr(nvme0):
    logging.info("user defined nvme init")

    nvme0[0x14] = 0
    while not (nvme0[0x1c]&0x1) == 0: pass

    # 3. set admin queue registers
    nvme0.init_adminq()

    # 4. set register cc
    if (nvme0.cap>>17) & 0x1:
        logging.info("set WRR arbitration")
        nvme0[0x14] = 0x00460800
    else:
        nvme0[0x14] = 0x00460000

    # 5. enable cc.en
    nvme0[0x14] = nvme0[0x14] | 1

    # 6. wait csts.rdy to 1
    while not (nvme0[0x1c]&0x1) == 1: pass

    # 7. identify controller
    nvme0.identify(Buffer(4096)).waitdone()

    # 8. create and identify all namespace
    nvme0.init_ns()

    # 9. set/get num of queues
    logging.debug("init number of queues")
    nvme0.setfeatures(0x7, cdw11=0xfffefffe).waitdone()
    cdw0 = nvme0.getfeatures(0x7).waitdone()
    nvme0.init_queues(cdw0)

@pytest.fixture()
def nvme0(pcie):
    return Controller(pcie, nvme_init_func=nvme_init_wrr)

@pytest.fixture()
def nvme0n1(nvme0):
    ret = Namespace(nvme0, 1, 0x10000)
    yield ret
    ret.close()


def test_ioworker_with_wrr(nvme0, nvme0n1):
    if (nvme0.cap>>17) & 0x1 == 0:
        pytest.skip("WRR is not supported")

    nvme0n1.format(512)

    # 8:4:2
    assert nvme0[0x14] == 0x00460801
    nvme0.setfeatures(1, cdw11=0x07030103).waitdone()
    cdw0 = nvme0.getfeatures(1).waitdone()
    assert cdw0 == 0x07030103

    l = []
    for i in range(3):
        a = nvme0n1.ioworker(io_size=8,
                             read_percentage=100,
                             region_end=0x10000,
                             qprio=i+1,
                             time=30)
        l.append(a)

    w = []
    for a in l:
        r = a.start()
        w.append(r)

    io_count = []
    for a in l:
        r = a.close()
        logging.debug(r)
        io_count.append(r.io_count_read)

    logging.info(io_count)
    assert io_count[1]/io_count[2] > 1.7
    assert io_count[1]/io_count[2] < 2.2
    assert io_count[0]/io_count[1] > 1.7
    assert io_count[0]/io_count[1] < 2.2


def test_weighed_round_robin(nvme0):
    if (nvme0.cap>>17) & 0x1 == 0:
        pytest.skip("WRR is not supported")

    assert nvme0[0x14] == 0x00460801
    nvme0.setfeatures(1, cdw11=0x07030103).waitdone()
    cdw0 = nvme0.getfeatures(1).waitdone()
    assert cdw0 == 0x07030103

    start = time.time()
    nvme0.getfeatures(7).waitdone()
    logging.info("admin latency: %f" % (time.time()-start))

    # create the senario of Figure 138 in NVMe spec v1.4
    # 1 admin, 2 urgent, 2 high, 2 medium, 2 low
    sq_list = []
    cq = IOCQ(nvme0, 1, 1024, PRP(1024*64))
    for i in range(8):
        sq_list.append(IOSQ(nvme0, i+1, 128, PRP(128*64), cqid=1, qprio=i//2))

    # fill 100 flush commands in each queue
    for sq in sq_list:
        for i in range(100):
            sq[i] = SQE(i<<16+0, 1)

    # fire all sq, low prio first
    for sq in sq_list[::-1]:
        sq.tail = 100

    # check the latency of admin command
    start = time.time()
    nvme0.getfeatures(7).waitdone()
    logging.info("admin latency when IO busy: %f" % (time.time()-start))

    # check sqid of the whole cq
    time.sleep(1)
    logging.info([cq[i][2]>>16 for i in range(100*8)])
    # assert all urgent IO completed first
    last_sqid = {cq[i][2]>>16 for i in range(300, 800)}
    assert 1 not in last_sqid
    assert 2 not in last_sqid

    # delete all queues
    for sq in sq_list:
        sq.delete()
    cq.delete()


def test_default_round_robin(nvme0):
    # 1 admin, 8 io queue
    sq_list = []
    cq = IOCQ(nvme0, 1, 1024, PRP(1024*64))
    for i in range(8):
        sq_list.append(IOSQ(nvme0, i+1, 128, PRP(128*64), cqid=1))

    # fill 100 flush commands in each queue
    for sq in sq_list:
        for i in range(100):
            sq[i] = SQE(i<<16+0, 1)

    # fire all sq, low prio first
    for sq in sq_list:
        sq.tail = 100

    # check the latency of admin command
    start = time.time()
    nvme0.getfeatures(7).waitdone()
    logging.info("admin latency when IO busy: %f" % (time.time()-start))

    # check sqid of the whole cq
    time.sleep(1)
    logging.debug([cq[i][2]>>16 for i in range(100*8)])
    # assert all urgent IO completed first
    last_sqid = {cq[i][2]>>16 for i in range(700, 800)}
    assert len(last_sqid) >= 7

    # delete all queues
    for sq in sq_list:
        sq.delete()
    cq.delete()
