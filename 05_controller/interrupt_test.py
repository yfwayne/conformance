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


@pytest.fixture(scope="function")
def ncqa(nvme0):
    num_of_queue = 0

    def test_greater_id(cdw0, status):
        nonlocal num_of_queue
        num_of_queue = 1+(cdw0 & 0xffff)
    nvme0.getfeatures(7, cb=test_greater_id).waitdone()
    logging.info("number of queue: %d" % num_of_queue)
    return num_of_queue


def get_aggregation_time_threshold(nvme0):
    time_threhold = 0

    def get_feature_cb(cdw0, status):
        nonlocal time_threhold
        time_threhold = cdw0 & 0xffff
    nvme0.getfeatures(8, cb=get_feature_cb).waitdone()
    logging.info("aggregation_time_threshold: 0x%x" % time_threhold)
    return time_threhold


def test_io_qpair_msix_interrupt_all(nvme0, nvme0n1, ncqa):
    buf = d.Buffer(4096)
    ql = []
    for i in range(ncqa):
        q = d.Qpair(nvme0, 8)
        ql.append(q)
        logging.info("qpair %d" % q.sqid)

        q.msix_clear()
        assert not q.msix_isset()
        nvme0n1.read(q, buf, 0, 8)
        time.sleep(0.1)
        assert q.msix_isset()
        q.waitdone()
    for q in ql:
        q.delete()


def test_io_qpair_msix_interrupt_mask(nvme0, nvme0n1, buf):
    q = d.Qpair(nvme0, 8)

    q.msix_clear()
    assert not q.msix_isset()
    nvme0n1.read(q, buf, 0, 8)
    time.sleep(1)
    assert q.msix_isset()
    q.waitdone()

    q.msix_clear()
    assert not q.msix_isset()
    nvme0n1.read(q, buf, 0, 8)
    time.sleep(1)
    assert q.msix_isset()
    q.waitdone()

    q.msix_clear()
    q.msix_mask()
    assert not q.msix_isset()
    nvme0n1.read(q, buf, 0, 8)
    assert not q.msix_isset()
    time.sleep(1)
    assert not q.msix_isset()
    q.msix_unmask()
    time.sleep(1)
    assert q.msix_isset()
    q.waitdone()

    q2 = d.Qpair(nvme0, 8)

    q.msix_clear()
    q2.msix_clear()
    assert not q.msix_isset()
    assert not q2.msix_isset()
    nvme0n1.read(q2, buf, 0, 8)
    time.sleep(1)
    assert not q.msix_isset()
    assert q2.msix_isset()
    q2.waitdone()

    q.delete()
    q2.delete()


def test_io_qpair_msix_interrupt_coalescing(nvme0, nvme0n1, buf, qpair):
    qpair.msix_clear()
    assert not qpair.msix_isset()

    # Get drvie interrupt aggregation time and threshold
    time_threhold = get_aggregation_time_threshold(nvme0)
    logging.info("interrupt aggregation time: %dus" %
                 ((time_threhold >> 8)*100))
    logging.info("interrupt aggregation threshold: %d" %
                 (time_threhold & 0xff))

    # 1 cmd, check interrupt latency
    nvme0n1.read(qpair, buf, 0, 8)
    start = time.time()
    while not qpair.msix_isset():
        pass
    latency1 = time.time()-start
    logging.info("interrupt latency %dus" % (latency1*1000000))
    qpair.waitdone()
    qpair.msix_clear()

    # aggregation time: 100*100us=0.01s, aggregation threshold: 2
    nvme0.setfeatures(8, cdw11=(200 << 8)+10).waitdone()

    # 2 cmd, check interrupt latency
    nvme0n1.read(qpair, buf, 0x8FFF, 8)
    nvme0n1.read(qpair, buf, 0x1600, 8)
    start = time.time()
    while not qpair.msix_isset():
        pass
    latency2 = time.time()-start
    logging.info("interrupt latency %dus" % (latency2*1000000))
    qpair.waitdone(2)
    qpair.msix_clear()

    # 1 cmd, check interrupt latency
    nvme0.setfeatures(8, cdw11=0).waitdone()
    nvme0n1.read(qpair, buf, 32, 8)
    start = time.time()
    while not qpair.msix_isset():
        pass
    latency1 = time.time()-start
    logging.info("interrupt latency %dus" % (latency1*1000000))
    qpair.waitdone()
    qpair.msix_clear()

    assert latency2 > latency1


def test_pcie_msix_cap_disable_ctrl(pcie, nvme0, nvme0n1, buf, qpair):
    msix_cap_addr = pcie.cap_offset(0x11)
    msix_ctrl = pcie.register(msix_cap_addr+2, 2)
    logging.info("msix_ctrl register [0x%x]= 0x%x" %
                 (msix_cap_addr+2, msix_ctrl))
    msix_table = pcie.register(msix_cap_addr+4, 4)
    logging.info("msix_table offset [0x%x]= 0x%x" %
                 (msix_cap_addr+4, msix_table))
    msix_pba = pcie.register(msix_cap_addr+8, 4)
    logging.info("msix_pba offset [0x%x]= 0x%x" % (msix_cap_addr+8, msix_pba))

    qpair.msix_clear()
    assert not qpair.msix_isset()
    nvme0n1.read(qpair, buf, 0, 8)
    time.sleep(0.1)
    assert qpair.msix_isset()
    qpair.waitdone()

    # Disable MSI-X bit
    qpair.msix_clear()
    pcie[msix_cap_addr+3] = (msix_ctrl >> 8) & 0x7F
    msix_ctrl = pcie.register(msix_cap_addr+2, 2)
    logging.info("After disable msi-x, msix_ctrl register [0x%x]= 0x%x" %
                 (msix_cap_addr+2, msix_ctrl))
    
    assert not qpair.msix_isset()
    nvme0n1.flush(qpair)
    time.sleep(1)
    assert not qpair.msix_isset()
    qpair.waitdone()

    # restore MSI-X bit
    pcie[msix_cap_addr+3] = (msix_ctrl >> 8) | 0x80
    msix_ctrl = pcie.register(msix_cap_addr+2, 2)
    logging.info("restore msix_ctrl register [0x%x]= 0x%x" %
                 (msix_cap_addr+2, msix_ctrl))
    
