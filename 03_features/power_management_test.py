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


import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_apst_enabled(nvme0):
    if not nvme0.id_data(265):
        pytest.skip("APST is not enabled")

    pass


def test_host_controlled_thermal_management_enabled(nvme0):
    if not nvme0.id_data(322, 323):
        pytest.skip("APST is not enabled")

    pass


@pytest.mark.parametrize("ps", [4, 3, 2, 1, 0])
def test_format_at_power_state(nvme0, nvme0n1, ps):
    nvme0.setfeatures(0x2, cdw11=ps).waitdone()
    assert nvme0n1.format(ses=0) == 0
    assert nvme0n1.format(ses=1) == 0
    p = nvme0.getfeatures(0x2).waitdone()
    assert p == ps

    
@pytest.mark.parametrize("ps_from", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("ps_to", [0, 1, 2, 3, 4])
def test_power_state_transition(pcie, nvme0, nvme0n1, qpair, buf, ps_from, ps_to):
    # for accurate sleep delay
    import ctypes
    libc = ctypes.CDLL('libc.so.6')

    # write data to LBA 0x5a
    nvme0n1.write(qpair, buf, 0x5a).waitdone()

    # enable ASPM and get original power state
    pcie.aspm = 2
    orig_ps = nvme0.getfeatures(0x2).waitdone()

    # disable apst
    nvme0.setfeatures(0xc).waitdone()
    
    # test with delay 1us-1ms
    for i in range(1000):
        # set beginning state
        nvme0.setfeatures(0x2, cdw11=ps_from).waitdone()
        libc.usleep(1000)

        # set end state
        nvme0.setfeatures(0x2, cdw11=ps_to)
        libc.usleep(i)

        # read lba 0x5a and verify data
        nvme0n1.read(qpair, buf, 0x5a).waitdone()
        assert buf[0] == 0x5a

        # consume the cpl of setfeatures above
        nvme0.waitdone()  # for setfeautres above

    # recover to original power state
    pcie.aspm = 0
    nvme0.setfeatures(0x2, cdw11=orig_ps).waitdone()


def test_power_state_transition_3_4(pcie, nvme0, nvme0n1, qpair, buf):
    # for accurate sleep delay
    import ctypes
    libc = ctypes.CDLL('libc.so.6')

    # write data to LBA 0x5a
    nvme0n1.write(qpair, buf, 0x5a).waitdone()

    # enable ASPM and get original power state
    pcie.aspm = 2
    orig_ps = nvme0.getfeatures(0x2).waitdone()

    # disable apst
    nvme0.setfeatures(0xc).waitdone()
    
    # test with delay 1us-1ms
    for i in range(1000):
        for (ps_from, ps_to) in [(0, 3), (3, 4), (0, 4)]:
            # set beginning state
            nvme0.setfeatures(0x2, cdw11=ps_from).waitdone()
            libc.usleep(1000)

            # set end state
            nvme0.setfeatures(0x2, cdw11=ps_to)
            libc.usleep(i)

            # read lba 0x5a and verify data
            nvme0n1.read(qpair, buf, 0x5a).waitdone()
            assert buf[0] == 0x5a

            # consume the cpl of setfeatures above
            nvme0.waitdone()  # for setfeautres above

    # recover to original power state
    pcie.aspm = 0
    nvme0.setfeatures(0x2, cdw11=orig_ps).waitdone()


