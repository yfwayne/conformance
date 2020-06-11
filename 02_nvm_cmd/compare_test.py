import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_compare_lba_0(nvme0, nvme0n1, buf, qpair):
    ncap = nvme0n1.id_data(15, 8)
    
    nvme0n1.write(qpair, buf, 0).waitdone()
    nvme0n1.compare(qpair, buf, 0).waitdone()

    with pytest.warns(UserWarning, match="ERROR status: 02/85"):
        nvme0n1.compare(qpair, buf, ncap-1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/85"):
        buf[0] += 1
        nvme0n1.compare(qpair, buf, 0).waitdone()

    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.compare(qpair, buf, ncap).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.compare(qpair, buf, 0xffffffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.compare(qpair, buf, 0xffffffff00000000).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.compare(qpair, buf, 0x100000000).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.compare(qpair, buf, ncap-1, 2).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0n1.compare(qpair, buf, ncap, 0x1000).waitdone()


def test_compare_invalid_nsid(nvme0, nvme0n1):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd compare, invalid namespace
    cmd = SQE(5, 0xff)
    buf = PRP(512)
    cmd.prp1 = buf
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    sq.delete()
    cq.delete()
    
