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

import nvme as d


def mi_vpd_write(nvme0, data, offset=0, length=256):
    nvme_status = 0
    mi_status = 0
    response = 0
    def mi_send_cb(dword0, status1):
        nonlocal nvme_status
        nonlocal mi_status
        nonlocal response
        nvme_status = (status1 >> 1)
        mi_status = (dword0 & 0xff)
        response = (dword0 >> 8)
    nvme0.mi_send(6, offset, length, data, cb=mi_send_cb).waitdone()
    assert nvme_status == 0
    return mi_status, response

def mi_vpd_read(nvme0, data, offset=0, length=256):
    nvme_status = 0
    mi_status = 0
    response = 0
    def mi_receive_cb(dword0, status1):
        nonlocal nvme_status
        nonlocal mi_status
        nonlocal response
        nvme_status = (status1 >> 1)
        mi_status = (dword0 & 0xff)
        response = (dword0 >> 8)
    nvme0.mi_receive(5, offset, length, data, cb=mi_receive_cb).waitdone()
    assert nvme_status == 0
    return mi_status, response

    
def test_vpd_write_and_read(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    write_buf = d.Buffer(256, pvalue=100, ptype=0xbeef)
    read_buf = d.Buffer(256)
    
    status, response = mi_vpd_write(nvme0, write_buf)
    assert status == 0
    assert response == 0
    
    status, response = mi_vpd_read(nvme0, read_buf)
    assert status == 0
    assert response == 0

    assert write_buf != read_buf
    assert write_buf[:] == read_buf[:]


def test_reset(nvme0, subsystem):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    nvme0.mi_send(7, 0).waitdone()
    nvme0.reset()


def test_invalid_operation(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    dword0 = nvme0.mi_send(0xbf).waitdone()
    assert dword0&0xff == 0x3


def test_configuration_get_invalid(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    dword0 = nvme0.mi_send(4, 1).waitdone()
    logging.info(hex(dword0))

    
def test_configuration_get_health_status_change(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    dword0 = nvme0.mi_send(4, 2).waitdone()
    logging.info(hex(dword0))


def test_configuration_set_health_status_change(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    dword0 = nvme0.mi_send(3, 2, 0).waitdone()
    logging.info(hex(dword0))


def test_read_nvme_mi_data_structure_nvm_subsystem_information(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    buf = d.Buffer(0x2000)
    dword0 = nvme0.mi_receive(0, 0, 0, buf).waitdone()
    logging.info(hex(dword0))
    logging.info(buf.dump(3))

# use mi_send to read nvme mi data structure: illegal
def test_read_nvme_mi_data_structure_nvm_subsystem_information_wrong_command(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    buf = d.Buffer(0x2000)
    dword0 = nvme0.mi_send(0, 0, 0, buf).waitdone()
    logging.info(hex(dword0))
    logging.info(buf.dump(3))
    

def test_read_nvme_mi_data_structure_port_information(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    buf = d.Buffer(0x2000)
    dword0 = nvme0.mi_receive(0, 1<<24, 0, buf).waitdone()
    logging.info(hex(dword0))
    logging.info(buf.dump(32))
    assert buf[0] == 1

    
def test_read_nvme_mi_data_structure_port_information_wrong_port(nvme0):
    if not nvme0.supports(0x1d) or not nvme0.supports(0x1e):
        pytest.skip("mi commands are not supported")
        
    buf = d.Buffer(0x2000)
    dword0 = nvme0.mi_receive(0, (1<<24)+(1<<16), 0, buf).waitdone()
    logging.info(hex(dword0))
    logging.info(buf.dump(32))
    
