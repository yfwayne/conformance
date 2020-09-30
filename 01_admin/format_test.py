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


def test_format_all_basic(nvme0, nvme0n1):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
    nvme0n1.format(512)
    
    nvme0.format(0).waitdone()
    nvme0.format(0, 0).waitdone()
    nvme0.format(0, 1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/0a"):
        nvme0.format(2, 0).waitdone()

    nvme0.format(0, 0, 0xffffffff).waitdone()
    nvme0.format(0, 1, 0xffffffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.format(0, 0, 0xfffffffb).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.format(0, 1, 0xfffffffb).waitdone()

    nvme0n1.format(512)
    nvme0.timeout = orig_timeout
        

def test_format_verify_data(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(4096)
    write_buf = Buffer(4096)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 1).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 0, 0xffffffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 1, 0xffffffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    # crypto erase
    fna = nvme0.id_data(524)
    if fna & 0x4:
        nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
        assert read_buf[10:21] == b'hello world'
        nvme0.format(0, 2, 0xffffffff).waitdone()
        nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
        assert read_buf[10:21] != b'hello world'

    nvme0n1.format(512)
    nvme0.timeout = orig_timeout
        

def test_format_invalid_ses(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(4096)
    write_buf = Buffer(4096)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    with pytest.warns(UserWarning, match="ERROR status: (00/02|01/0a)"):
        nvme0.format(0, 7, 0xffffffff).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    
    nvme0n1.format(512)
    nvme0.timeout = orig_timeout

    
def test_format_invalid_lbaf(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(4096)
    write_buf = Buffer(4096)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    
    with pytest.warns(UserWarning, match="ERROR status: 01/0a"):
        nvme0.format(2).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'        
    
    with pytest.warns(UserWarning, match="ERROR status: (00/02|01/0a)"):
        nvme0.format(0, 7).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'        

    nvme0n1.format(512)
    nvme0.timeout = orig_timeout
    
