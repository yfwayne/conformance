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
    
