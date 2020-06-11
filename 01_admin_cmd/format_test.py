import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_format_all_basic(nvme0):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
    
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

    nvme0.timeout = orig_timeout
        

def test_format_verify_data(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 0).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 0, 0xffffffff).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] != b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    nvme0.format(0, 1, 0xffffffff).waitdone()
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

    nvme0.timeout = orig_timeout
        

def test_format_invalid_ses(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.format(0, 7, 0xffffffff).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    
    nvme0.timeout = orig_timeout

    
def test_format_invalid_lbaf(nvme0, nvme0n1, verify, qpair):
    if not nvme0.supports(0x80):
        pytest.skip("format is not support")

    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
        
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
    
    with pytest.warns(UserWarning, match="ERROR status: 01/0a"):
        nvme0.format(2).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'        
    
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.format(0, 7).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'        

    nvme0.timeout = orig_timeout
    