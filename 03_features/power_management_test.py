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


def read_write_8M(nvme0n1, qpair):
    buf128k = Buffer(128*1024)
    lba128k = 128*1024//512

    # write all data
    slba = 0x10000
    for i in range(64):
        nvme0n1.write(qpair, buf128k, slba, lba128k)
        slba += lba128k
    qpair.waitdone(64)

    # read all data
    slba = 0x10000
    for i in range(64):
        nvme0n1.read(qpair, buf128k, slba, lba128k)
        slba += lba128k
    qpair.waitdone(64)
            
    
@pytest.mark.parametrize("ps_from", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("ps_to", [0, 1, 2, 3, 4])
def test_power_state_transition(pcie, nvme0, nvme0n1, buf, qpair, ps_from, ps_to):
    # for accurate sleep delay
    import ctypes
    libc = ctypes.CDLL('libc.so.6')

    # enable ASPM and get original power state
    pcie.aspm = 2
    orig_ps = nvme0.getfeatures(0x2).waitdone()

    # disable apst
    nvme0.setfeatures(0xc, buf=buf).waitdone()

    # write data to LBA 0x5a
    buf = Buffer(512, ptype=32, pvalue=0x5a5a5a5a)
    nvme0n1.write(qpair, buf, 0x5a).waitdone()

    # test with delay 1us-1ms
    for delay in range(1000):
        # set beginning state
        nvme0.setfeatures(0x2, cdw11=ps_from).waitdone()
        libc.usleep(1000)

        # write and read data to invalidate cache
        read_write_8M(nvme0n1, qpair)

        # set end state
        nvme0.setfeatures(0x2, cdw11=ps_to)
        libc.usleep(delay)

        # read lba 0x5a and verify data
        nvme0n1.read(qpair, buf, 0x5a).waitdone()
        assert buf[0] == 0x5a
        for i in range(8, 512-8):
            assert buf[i] == 0x5a

        # consume the cpl of setfeatures above
        nvme0.waitdone()  # for setfeautres above

    # recover to original power state
    pcie.aspm = 0
    nvme0.setfeatures(0x2, cdw11=orig_ps).waitdone()


def test_power_state_transition_0_3_4(pcie, nvme0, nvme0n1, qpair, buf):
    # for accurate sleep delay
    import ctypes
    libc = ctypes.CDLL('libc.so.6')

    # enable ASPM and get original power state
    pcie.aspm = 2
    orig_ps = nvme0.getfeatures(0x2).waitdone()

    # disable apst
    nvme0.setfeatures(0xc, buf=buf).waitdone()

    # write data to LBA 0x5a
    buf = Buffer(512, ptype=32, pvalue=0x5a5a5a5a)
    nvme0n1.write(qpair, buf, 0x5a).waitdone()
    
    # test with delay 1us-10ms, 100 times each us
    for delay in range(10000):
        # write and read data to invalidate cache
        read_write_8M(nvme0n1, qpair)
        
        # PS0
        nvme0.setfeatures(0x2, cdw11=0).waitdone()
        libc.usleep(1000)
        
        # PS3, read, and PS4
        nvme0.setfeatures(0x2, cdw11=3)
        libc.usleep(delay)
        nvme0n1.read(qpair, buf, 0x5a)
        nvme0.setfeatures(0x2, cdw11=4)

        # check read result
        qpair.waitdone()
        assert buf[0] == 0x5a
        for i in range(8, 512-8):
            assert buf[i] == 0x5a

        # consume the cpl of setfeatures above
        nvme0.waitdone(2)

    # recover to original power state
    pcie.aspm = 0
    nvme0.setfeatures(0x2, cdw11=orig_ps).waitdone()


def test_power_state_async_with_io(pcie, nvme0, nvme0n1, buf, verify, duration=100):
    # for accurate sleep delay
    import ctypes
    libc = ctypes.CDLL('libc.so.6')

    # enable ASPM and get original power state
    pcie.aspm = 2
    orig_ps = nvme0.getfeatures(0x2).waitdone()

    # disable apst
    nvme0.setfeatures(0xc, buf=buf).waitdone()

    # start with PS0
    nvme0.setfeatures(0x2, cdw11=0).waitdone()
    
    # fill data for verify
    nvme0n1.ioworker(io_size=8,
                     lba_random=False,
                     read_percentage=0, 
                     region_end=1024*1024,
                     io_count=1024*1024//8).start().close()

    #mix read and PS setting
    w = nvme0n1.ioworker(io_size=8,
                         lba_random=True,
                         read_percentage=100, 
                         region_end=1024*1024,
                         iops=1000, 
                         time=duration).start()
    while w.running:
        nvme0.setfeatures(0x2, cdw11=3).waitdone()
        libc.usleep(999)
        nvme0.setfeatures(0x2, cdw11=4).waitdone()
        libc.usleep(999)
    w.close()
