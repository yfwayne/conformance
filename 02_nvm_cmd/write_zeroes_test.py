import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_write_zeroes_large_lba(nvme0, nvme0n1, buf, qpair):
    ncap = nvme0n1.id_data(15, 8)
    
    nvme0n1.write_zeroes(qpair, ncap-1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_zeroes(qpair, ncap).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_zeroes(qpair, ncap+1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_zeroes(qpair, ncap-1, 2).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_zeroes(qpair, 0xffffffff00000000).waitdone()


@pytest.mark.parametrize("ioflag", [0, 0x4000, 0x8000, 0xc000])
def test_write_zeroes_valid(nvme0, nvme0n1, ioflag, qpair):
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 1).waitdone()
    assert read_buf[0] == 1
    
    # send write and read command
    def write_cb(cdw0, status1):  # command callback function
        nvme0n1.read(qpair, read_buf, 1)
    nvme0n1.write_zeroes(qpair, 1, 1, io_flags=ioflag, cb=write_cb)

    # wait commands complete and verify data
    assert read_buf[0] == 1
    qpair.waitdone(2)
    assert read_buf[0] == 0
        

def test_write_zeroes_invalid_nsid(nvme0, nvme0n1):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(8, 0xff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    sq.delete()
    cq.delete()
    
    
def test_write_zeroes_invalid_nlb(nvme0, nvme0n1):
    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(8, 1)
    cmd[12] = mdts//512
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0

    sq.delete()
    cq.delete()
    
    
def test_write_zeroes_invalid_nsid_lba(nvme0, nvme0n1):
    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(8, 0xff)
    buf = PRP(512)
    cmd.prp1 = buf
    cmd[10] = ncap&0xffffffff
    cmd[11] = ncap>>32
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b  # invalid namespace or format

    sq.delete()
    cq.delete()
    
