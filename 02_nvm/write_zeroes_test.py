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

    
def test_write_zeroes_large_lba(nvme0, nvme0n1, buf, qpair):
    if not nvme0n1.supports(0x8):
        pytest.skip("Write zeroes is not supported")
    
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
    if not nvme0n1.supports(0x8):
        pytest.skip("Write zeroes is not supported")    
    
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
        

def test_write_zeroes_invalid_nsid(nvme0, nvme0n1, cq, sq):
    if not nvme0n1.supports(0x8):
        pytest.skip("Write zeroes is not supported")

    # first cmd, invalid namespace
    cmd = SQE(8, 0xff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    
def test_write_zeroes_invalid_nlb(nvme0, nvme0n1, cq, sq):
    if not nvme0n1.supports(0x8):
        pytest.skip("Write zeroes is not supported")

    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts

    # first cmd, invalid namespace
    cmd = SQE(8, 1)
    cmd[12] = mdts//512
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0

    
def test_write_zeroes_invalid_nsid_lba(nvme0, nvme0n1, cq, sq):
    if not nvme0n1.supports(0x8):
        pytest.skip("Write zeroes is not supported")    

    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
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

