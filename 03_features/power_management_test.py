import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_apst_enabled(nvme0):
    if not nvme0.id_data(265):
        pytest.skip("APST is not enabled")

    pass


def test_host_controlled_thermal_management_enabled(nvme0):
    if not nvme0.id_data(322, 323):
        pytest.skip("APST is not enabled")

    pass


@pytest.mark.parametrize("ps", [4, 3, 2, 1, 0])
def test_format_at_power_state(nvme0, nvme0n1, ps):
    nvme0.setfeatures(0x2, cdw11=ps).waitdone()
    assert nvme0n1.format(ses=0) == 0
    assert nvme0n1.format(ses=1) == 0
    p = nvme0.getfeatures(0x2).waitdone()
    assert p == ps

