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

