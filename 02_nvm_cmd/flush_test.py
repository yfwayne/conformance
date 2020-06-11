import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_flush_with_read_write(nvme0, nvme0n1, qpair):
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    # send write and read command
    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.flush(qpair).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'


def test_read_invalid_nsid(nvme0, nvme0n1):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(0, 0xff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    sq.delete()
    cq.delete()
    
    
def test_read_all_namespace(nvme0, nvme0n1):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(0, 0xffffffff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0

    sq.delete()
    cq.delete()
    
    
