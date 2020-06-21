import time
import pytest
import logging

import nvme as d


@pytest.fixture(scope="function")
def ncqa(nvme0):
    num_of_queue = 0
    def test_greater_id(cdw0, status):
        nonlocal num_of_queue
        num_of_queue = 1+(cdw0&0xffff)
    nvme0.getfeatures(7, cb=test_greater_id).waitdone()
    logging.info("number of queue: %d" % num_of_queue)
    return num_of_queue


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

    # aggregation time: 100*100us=0.01s, aggregation threshold: 2
    nvme0.setfeatures(8, cdw11=(200<<8)+10)

    # 1 cmd, check interrupt latency
    nvme0n1.read(qpair, buf, 0, 8)
    start = time.time()
    while not qpair.msix_isset(): pass
    latency1 = time.time()-start
    logging.info("interrupt latency %dus" % (latency1*1000000))
    qpair.waitdone()
    qpair.msix_clear()

    # 2 cmd, check interrupt latency
    nvme0n1.read(qpair, buf, 0, 8)
    nvme0n1.read(qpair, buf, 0, 8)
    start = time.time()
    while not qpair.msix_isset(): pass
    latency2 = time.time()-start
    logging.info("interrupt latency %dus" % (latency2*1000000))
    qpair.waitdone(2)
    qpair.msix_clear()

    # 1 cmd, check interrupt latency
    nvme0n1.read(qpair, buf, 0, 8)
    start = time.time()
    while not qpair.msix_isset(): pass
    latency1 = time.time()-start
    logging.info("interrupt latency %dus" % (latency1*1000000))
    qpair.waitdone()
    qpair.msix_clear()
    qpair.delete()

    assert latency2 < latency1

