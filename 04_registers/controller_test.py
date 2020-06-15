import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_controller_cap(nvme0):
    logging.info("cap: 0x%lx" % nvme0.cap)
    
    mps_min = (nvme0.cap>>48) & 0xf
    mps_max = (nvme0.cap>>52) & 0xf
    assert mps_max >= mps_min

    css = (nvme0.cap>>37) & 0xff
    assert css == 1

    
def test_controller_version(nvme0):
    logging.info("cap: 0x%x" % nvme0[8])
    assert (nvme0[8]>>16) == 1


def test_controller_cc(nvme0):
    logging.info("cc: 0x%x" % nvme0[0x14])
    assert (nvme0[0x14]>>16) == 0x46

    
def test_controller_reserved(nvme0):
    assert nvme0[0x18] == 0

    
def test_controller_csts(nvme0):
    logging.info("csts: 0x%x" % nvme0[0x1c])
    assert nvme0[0x1c]&1 == 1
