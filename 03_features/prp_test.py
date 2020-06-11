import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


# TODO: invalid prp1/prp2 with identify cmd


def test_create_cq_with_invalid_prp_offset(nvme0):
    prp = PRP(4096)

    prp.offset = 2048
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

    prp.offset = 2048
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


def test_page_base_address_and_offset(nvme0, buf):
    nvme0.identify(buf).waitdone()


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

    
