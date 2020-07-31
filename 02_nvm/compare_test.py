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
    oncs = nvme0.id_data(521, 520)
    if oncs & 0x1 == 0:
        pytest.skip("Compare command is not supported")

    ncap = nvme0n1.id_data(15, 8)
    nvme0n1.write(qpair, buf, 1, 1).waitdone()
    nvme0n1.write(qpair, buf, 0, 1).waitdone()
    nvme0n1.compare(qpair, buf, 0).waitdone()

    orig = buf[0]
    with pytest.warns(UserWarning, match="ERROR status: 02/85"):
        nvme0n1.compare(qpair, buf, ncap-1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/85"):
        buf[0] += 1
        nvme0n1.compare(qpair, buf, 0).waitdone()
    buf[0] = orig                                                       
    with pytest.warns(UserWarning, match="ERROR status: 02/85"):          
        nvme0n1.compare(qpair, buf, 0, 2).waitdone()  

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
    with pytest.warns(UserWarning, match="ERROR status: 00/(02|80)"):        
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
    # check if fused commands supported
    if nvme0.id_data(523, 522) == 0:
        pytest.skip("fused command is not supported")

    # not fused,compare and write as separate command
    nvme0n1.write(qpair, buf, 8).waitdone()
    nvme0n1.compare(qpair, buf, 8).waitdone()
    # check if there is any Media and Data Integrity Errors
    with pytest.warns(UserWarning, match="ERROR status: 02/85"):
        logging.info("Compare failure!")

    # fused with correct order, compare 1st as the 1st cmd 
    nvme0n1.send_cmd(5|(1<<8), qpair, buf, 1, 8, 0, 0)
    nvme0n1.send_cmd(1|(1<<9), qpair, buf, 1, 8, 0, 0)
    qpair.waitdone(2)
    
    # atomic: first cmd should be timeout
    with pytest.warns(UserWarning, match="ERROR status: 00/0a"):
        # wrong order: send write cmd 1st as 1st cmd, should abort
        nvme0n1.send_cmd(1|(1<<8), qpair, buf, 1, 8, 0, 0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0a"):
        # wrong order: send compare cmd 2nd as 2nd cmd, should abort
        nvme0n1.send_cmd(5|(1<<9), qpair, buf, 1, 8, 0, 0).waitdone()

        
def test_fused_cmd_not_supported(nvme0, nvme0n1, qpair, buf):
    # check if fused commands supported
    if nvme0.id_data(523, 522) == 0:
        logging.info("fused command is not supported")

        # write to init buffer before compare
        nvme0n1.write(qpair, buf, 8).waitdone()
        
        # if fuse not supported, fuse command should abort with invalid field
        logging.info("fused command is not supported, abort!")
        with pytest.warns(UserWarning, match="ERROR status: 00/02"):
            nvme0n1.send_cmd(5|(1<<8), qpair, buf, 1, 8, 0, 0)
            nvme0n1.send_cmd(1|(1<<9), qpair, buf, 1, 8, 0, 0)
            qpair.waitdone(2)
    
