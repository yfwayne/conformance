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


# PCIe, different of power states and resets
@pytest.mark.skip(reason="subsystem")
def test_power_and_reset(pcie, nvme0, subsystem):
    pcie.aspm = 2              # ASPM L1
    pcie.power_state = 3       # PCI PM D3hot
    pcie.aspm = 0
    pcie.power_state = 0

    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    pcie.reset()               # PCIe reset: hot reset, TS1, TS2
    nvme0.reset()              # reset controller after pcie reset
    nvme0.getfeatures(7).waitdone()

    subsystem.reset()          # NVMe subsystem reset: NSSR
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    subsystem.power_cycle(10)  # power cycle NVMe device: cold reset
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    subsystem.poweroff()
    subsystem.poweron()
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()


@pytest.mark.parametrize("delay", [1]) #, 0.1, 0.01, 0.001, 0.0001, 0])
def test_reset_with_outstanding_io(nvme0, nvme0n1, delay, io_count=1000):
    nvme0n1.format(512)
    logging.debug("format done")
    
    cq = IOCQ(nvme0, 1, 1024, PRP(1024*64))
    sq = IOSQ(nvme0, 1, 1024, PRP(1024*64), cqid=1)

    write_cmd = SQE(1, 1)
    write_cmd[12] = 7  # 4K write
    buf_list = []
    for i in range(io_count):
        buf = PRP(ptype=32, pvalue=i)  # use cid as data pattern
        buf_list.append(buf)
        write_cmd.prp1 = buf
        write_cmd.cid = i
        write_cmd[10] = i
        sq[i] = write_cmd
    sq.tail = io_count

    # reset while io is active
    logging.debug("write done")
    time.sleep(delay)
    nvme0.reset()
    
    # read after reset with outstanding writes
    cq = IOCQ(nvme0, 1, 1024, PRP(1024*64))
    sq = IOSQ(nvme0, 1, 1024, PRP(1024*64), cqid=1)

    read_cmd = SQE(2, 1)
    read_cmd[12] = 7  # 4K read
    buf_list = []
    for i in range(io_count):
        buf = PRP()
        buf_list.append(buf)
        read_cmd.prp1 = buf
        read_cmd.cid = i
        read_cmd[10] = i
        sq[i] = read_cmd
    sq.tail = io_count
    logging.debug("read done")

    # data verify
    time.sleep(3)
    assert cq[io_count-1].p != 0
    for i in range(io_count):
        cid = cq[i].cid
        dp = buf_list[cq[i].cid].data(3, 0)  # check data pattern
        logging.debug("cpl %d: cid %d, data pattern %d" % (i, cid, dp))
        assert dp == 0 or dp == cid
        
    sq.delete()
    cq.delete()
    
