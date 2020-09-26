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

    
def test_read_large_lba(nvme0, nvme0n1, buf, qpair):
    ncap = nvme0n1.id_data(15, 8)
    
    nvme0n1.read(qpair, buf, ncap-1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, ncap).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, ncap+1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, ncap-1, 2).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, 0xffffffff00000000).waitdone()


@pytest.mark.parametrize("repeat", range(32))
def test_read_max_namespace_size(nvme0, nvme0n1, buf, repeat, qpair):
    nsze = nvme0n1.id_data(7, 0)
    ncap = nvme0n1.id_data(15, 8)
    assert nsze == ncap
    
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, nsze+repeat).waitdone()

    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, 0xffffffff+repeat).waitdone()
    
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        nvme0n1.read(qpair, buf, 0xffffffffffffffff-repeat).waitdone()
    

def test_read_fua(nvme0, nvme0n1, buf, qpair):
    for i in range(100):
        # read with FUA enabled
        nvme0n1.read(qpair, buf, 0, 8, 1<<30).waitdone()


def test_read_bad_number_blocks(nvme0, nvme0n1, qpair):
    if nvme0.mdts == 1024*1024: # up to 1MB
        pytest.skip("mdts is maximum")
        
    mdts = nvme0.mdts//512
    buf = Buffer(mdts*512+4096)

    nvme0n1.read(qpair, buf, 0, mdts-1).waitdone()
    nvme0n1.read(qpair, buf, 0, mdts).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0n1.read(qpair, buf, 0, mdts+1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0n1.read(qpair, buf, 0, mdts+2).waitdone()

    nlb = 1
    while nlb < mdts:
        nvme0n1.read(qpair, buf, 0, nlb).waitdone()
        nlb = nlb<<1

        
@pytest.mark.parametrize("ioflag", [0, 0x4000, 0x8000, 0xc000])
def test_read_valid(nvme0, nvme0n1, ioflag, qpair):
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    # send write and read command
    def write_cb(cdw0, status1):  # command callback function
        nvme0n1.read(qpair, read_buf, 0, 1, io_flags=ioflag)
    nvme0n1.write(qpair, write_buf, 0, 1, cb=write_cb)

    # wait commands complete and verify data
    assert read_buf[10:21] != b'hello world'
    qpair.waitdone(2)
    assert read_buf[10:21] == b'hello world'


def test_read_invalid_nsid(nvme0, nvme0n1, cq, sq):
    # first cmd, invalid namespace
    cmd = SQE(2, 0xff)
    buf = PRP(512)
    cmd.prp1 = buf
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    
def test_read_invalid_nlb(nvme0, nvme0n1, cq, sq):
    if nvme0.mdts == 1024*1024: # up to 1MB
        pytest.skip("mdts is maximum")
    
    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
    # first cmd, invalid namespace
    cmd = SQE(2, 1)
    buf = PRP(512)
    cmd.prp1 = buf
    cmd[12] = mdts//512
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x0002  # invalid field

    
def test_read_invalid_nsid_lba(nvme0, nvme0n1, cq, sq):
    ncap = nvme0n1.id_data(15, 8)
    mdts = nvme0.mdts
    
    # first cmd, invalid namespace
    cmd = SQE(2, 0xff)
    buf = PRP(512)
    cmd.prp1 = buf
    cmd[10] = ncap&0xffffffff
    cmd[11] = ncap>>32
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b  # invalid namespace or format

    
def test_read_invalid_prp_address_offset(nvme0, cq, sq):
    # first cmd, invalid prp offset
    buf = PRP(4096, ptype=0xbeef, pvalue=100)
    first_byte = buf[0]
    logging.info(buf.dump(16))
    
    cmd = SQE(1, 1)
    buf.offset = 1
    cmd.prp1 = buf
    cmd[10] = 1
    cmd[11] = 0
    cmd[12] = 1
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    
    if status == 0:
        # write success, check data
        cmd = SQE(2, 1)
        buf = PRP(4096)
        cmd.prp1 = buf
        cmd[10] = 1
        cmd[11] = 0
        cmd[12] = 1
        sq[1] = cmd
        sq.tail = 2
        time.sleep(0.1)
        status = (cq[1][3]>>17)&0x7ff
        assert status == 0
        logging.info(buf.dump(16))
        assert first_byte == buf[0]
    else:
        assert status == 0x0013  # invalid namespace or format

