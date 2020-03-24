import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_identify_all_nsid(nvme0):
    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0, cns=1).waitdone()
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=0xff, cns=0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=2, cns=0).waitdone()


def test_identify_namespace_id_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")
        
    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0x10).waitdone()
    nvme0.identify(buf, nsid=0, cns=0x10).waitdone()


def test_identify_active_controller_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=1, cns=0x12).waitdone()

    
def test_identify_controller_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=1, cns=0x13).waitdone()

    
def test_identify_global_namespace(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0).waitdone()


def test_identify_namespace(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0).waitdone()
    

def test_identify_namespace_list(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=2).waitdone()
    assert buf[0] == 1
    assert buf[16] == 0
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    assert buf[0] != 0
    assert buf[0] == buf[16]
    

def test_identify_namespace_identification_descriptor(nvme0, buf):
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=0, cns=3).waitdone()
        
    nvme0.identify(buf, nsid=1, cns=3).waitdone()
    assert buf[0] != 0
    print(buf.dump(64))


def test_identify_reserved_cns(nvme0, buf):
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.identify(buf, nsid=0, cns=0xff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.identify(buf, nsid=1, cns=0xff).waitdone()
    
