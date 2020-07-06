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


@pytest.mark.parametrize("nsid", [0, 2, 3, 128, 255, 0xffff, 0xfffffffe, 0xffffffff])
def test_compare_invalid_nsid(nvme0, nvme0n1, nsid):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd compare, invalid namespace
    cmd = SQE(5, nsid)
    buf = PRP(512)
    cmd.prp1 = buf
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    sq.delete()
    cq.delete()
    

def test_fused_operations(nvme0, nvme0n1, qpair, buf):
    # compare and write
    nvme0n1.write(qpair, buf, 8).waitdone()
    nvme0n1.compare(qpair, buf, 8).waitdone()

    # fused
    nvme0n1.send_cmd(5|(1<<8), qpair, buf, 1, 8, 0, 0)
    nvme0n1.send_cmd(1|(1<<9), qpair, buf, 1, 8, 0, 0)
    qpair.waitdone(2)

    # atomic: first cmd should be timeout
    with pytest.warns(UserWarning, match="ERROR status: 00/0a"):
        nvme0n1.send_cmd(1|(1<<8), qpair, buf, 1, 8, 0, 0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0a"):
        nvme0n1.send_cmd(5|(1<<9), qpair, buf, 1, 8, 0, 0).waitdone()

    qpair.delete()
    
