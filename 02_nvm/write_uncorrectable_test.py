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


@pytest.fixture()
def cq(nvme0):
    ret = IOCQ(nvme0, 1, 10, PRP())
    yield ret
    ret.delete()

@pytest.fixture()
def sq(nvme0, cq):
    ret = IOSQ(nvme0, 1, 10, PRP(), cq.id)
    yield ret
    ret.delete()


def test_write_uncorrectable_large_lba(nvme0, nvme0n1, buf, qpair):
    if not nvme0n1.supports(0x4):
        pytest.skip("Write Uncorrectable is not supported")

    ncap = nvme0n1.id_data(15, 8)
    
    nvme0n1.write_uncorrectable(qpair, ncap-1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_uncorrectable(qpair, ncap).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_uncorrectable(qpair, ncap+1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_uncorrectable(qpair, ncap-1, 2).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.write_uncorrectable(qpair, 0xffffffff00000000).waitdone()


@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_after_write_uncorrectable(nvme0, nvme0n1, repeat, qpair, 
                                              lba_start=0, lba_step=8, lba_count=8):
    if not nvme0n1.supports(0x4):
        pytest.skip("Write Uncorrectable is not supported")

    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supported")


    buf = Buffer(4096)
    pattern = repeat + (repeat<<8) + (repeat<<16) + (repeat<<24)
    write_buf = Buffer(4096, "write", pattern, 32)

    nvme0n1.write_uncorrectable(qpair, lba_start+repeat*lba_step, lba_count).waitdone()
    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(qpair, buf, 1).waitdone()
    nvme0n1.write(qpair, write_buf, lba_start+repeat*lba_step, lba_count).waitdone()

    
@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_before_write_uncorrectable(nvme0, nvme0n1, repeat, qpair, 
                                              lba_start=0, lba_step=8, lba_count=8):
    if not nvme0n1.supports(0x4):
        pytest.skip("Write Uncorrectable is not supported")

    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supported")

    buf = Buffer(4096)
    pattern = repeat + (repeat<<8) + (repeat<<16) + (repeat<<24)
    write_buf = Buffer(4096, "write", pattern, 32)
    q = Qpair(nvme0, 8)

    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(qpair, buf, 1).waitdone()
    nvme0n1.write_uncorrectable(qpair, lba_start+repeat*lba_step, lba_count).waitdone()
    nvme0n1.write(qpair, write_buf, lba_start+repeat*lba_step, lba_count).waitdone()

    
@pytest.mark.parametrize("repeat", range(32))
def test_write_uncorrectable_read(nvme0, nvme0n1, repeat, qpair, 
                                  lba_start=0, lba_step=8, lba_count=8):
    if not nvme0n1.supports(0x4):
        pytest.skip("Write Uncorrectable is not supported")

    buf = Buffer(4096)
    read_buf = Buffer(4096, "read")
    pattern = repeat + (repeat<<8) + (repeat<<16) + (repeat<<24)
    write_buf = Buffer(4096, "write", pattern, 32)

    nvme0n1.write_uncorrectable(qpair, lba_start+repeat*lba_step, lba_count).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    nvme0n1.write(qpair, write_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    nvme0n1.read(qpair, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    for i in range(lba_count):
        assert read_buf[i*512 + 10] == repeat


def test_write_uncorrectable_invalid_nlb(nvme0, nvme0n1, cq, sq):
    if not nvme0n1.supports(0x4):
        pytest.skip("Write Uncorrectable is not supported")

    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
    # first cmd, invalid namespace
    cmd = SQE(4, 1)
    cmd[12] = mdts//512
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0
