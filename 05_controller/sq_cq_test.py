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
    sq[1] = SQE(1<<16+0, 1); sq.tail = 0

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
        sq.delete()
    cq.delete()

    
def test_sq_doorbell_invalid2(nvme0):
    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 2, PRP(), cqid=1)
    sq.tail = 3
    
    time.sleep(0.1)
    #Invalid Doorbell Write Value
    with pytest.warns(UserWarning, match="AER notification is triggered: 0x10100"):
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
    
