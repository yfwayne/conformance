import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_controller_registers(nvme0):
    mps_min = (nvme0.cap>>48) & 0xf
    mps_max = (nvme0.cap>>52) & 0xf
    assert mps_max >= mps_min

    css = (nvme0.cap>>37) & 0xff
    assert css == 1
