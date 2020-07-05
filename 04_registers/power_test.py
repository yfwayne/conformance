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


def test_pcie_pmcsr_d3hot(pcie, nvme0, buf):
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    with pytest.raises(TimeoutError):
        with pytest.warns(UserWarning, match="ERROR status: 07/ff"):
            nvme0.identify(buf).waitdone()

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    
def test_pcie_capability_d3hot(pcie, nvme0n1):
    # get pm register
    assert None != pcie.cap_offset(1)
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    assert pcie.power_state == 0

    # set d3hot
    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)

    # and exit d3hot
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    # again
    pcie.power_state = 0
    logging.info("curent power state: %d" % pcie.power_state)
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.power_state == 0
    

def test_pcie_aspm_l1_and_d3hot(pcie, nvme0n1):
    pcie.aspm = 2
    assert pcie.aspm == 2
    pcie.power_state = 3
    time.sleep(1)
    pcie.power_state = 0
    pcie.aspm = 0
    assert pcie.aspm == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    pcie.power_state = 3
    assert pcie.power_state == 3
    pcie.aspm = 2
    time.sleep(1)
    pcie.aspm = 0
    assert pcie.aspm == 0
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.aspm == 0

    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()


    
