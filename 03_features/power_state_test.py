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
