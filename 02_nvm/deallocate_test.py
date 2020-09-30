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


@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_and_write(nvme0, nvme0n1, repeat, qpair, 
                              lba_start=1, lba_step=3, lba_count=3):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    pattern = repeat + (repeat<<8) + (repeat<<16) + (repeat<<24)
    write_buf = Buffer(4096, "write", pattern, 32)
    read_buf = Buffer(4096, "read")
    
    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(qpair, buf, 1).waitdone()
    nvme0n1.write(qpair, write_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    nvme0n1.read(qpair, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()
    for i in range(lba_count):
        assert read_buf[i*512 + 10] == repeat
        

@pytest.mark.parametrize("repeat", range(32))
def test_deallocate_and_read(nvme0, nvme0n1, repeat, qpair, 
                             lba_start=1, lba_step=3, lba_count=3):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    read_buf = Buffer(4096, "read")
    
    buf.set_dsm_range(0, lba_start+repeat*lba_step, lba_count)
    nvme0n1.dsm(qpair, buf, 1).waitdone()
    nvme0n1.read(qpair, read_buf, lba_start+repeat*lba_step, lba_count).waitdone()


def test_deallocate_out_of_range(nvme0, nvme0n1, qpair): 
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    ncap = nvme0n1.id_data(15, 8)
    buf = Buffer(4096)

    buf.set_dsm_range(0, ncap-1, 1)
    nvme0n1.dsm(qpair, buf, 1).waitdone()
    
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        buf.set_dsm_range(0, ncap, 1)
        nvme0n1.dsm(qpair, buf, 1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/80"):
        buf.set_dsm_range(0, ncap-1, 2)
        nvme0n1.dsm(qpair, buf, 1).waitdone()


def test_deallocate_nr_maximum(nvme0, nvme0n1, qpair): 
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)

    for i in range(256):
        buf.set_dsm_range(i, i, 1)
    nvme0n1.dsm(qpair, buf, 256).waitdone()

    with pytest.raises(IndexError):
        for i in range(257):
            buf.set_dsm_range(i, i, 1)
    nvme0n1.dsm(qpair, buf, 257).waitdone()
    

def test_deallocate_correct_range(nvme0, nvme0n1, qpair):
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    nvme0n1.write(qpair, buf, 1, 3).waitdone()
    
    buf.set_dsm_range(0, 2, 1)
    nvme0n1.dsm(qpair, buf, 1).waitdone()

    nvme0n1.read(qpair, buf, 1, 1).waitdone()
    logging.info(buf[0:4])
    assert buf[0] == 1
    nvme0n1.read(qpair, buf, 2, 1).waitdone()
    logging.info(buf[0:4])
    nvme0n1.read(qpair, buf, 3, 1).waitdone()
    logging.info(buf[0:4])
    assert buf[0] == 3

    
def test_deallocate_multiple_range(nvme0, nvme0n1, qpair): 
    if not nvme0n1.supports(0x9):
        pytest.skip("dsm is not supprted")

    buf = Buffer(4096)
    nvme0n1.write(qpair, buf, 1, 4).waitdone()
    
    buf.set_dsm_range(0, 1, 1)
    buf.set_dsm_range(1, 2, 1)
    buf.set_dsm_range(2, 3, 1)
    nvme0n1.dsm(qpair, buf, 3).waitdone()

    nvme0n1.read(qpair, buf, 1, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(qpair, buf, 2, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(qpair, buf, 3, 1).waitdone()
    logging.debug(buf[0:4])
    nvme0n1.read(qpair, buf, 4, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 4
    
    nvme0n1.write(qpair, buf, 1, 4).waitdone()
    nvme0n1.read(qpair, buf, 1, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 1
    nvme0n1.read(qpair, buf, 2, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 2
    nvme0n1.read(qpair, buf, 3, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 3
    nvme0n1.read(qpair, buf, 4, 1).waitdone()
    logging.debug(buf[0:4])
    assert buf[0] == 4
