import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_verify_valid(nvme0, nvme0n1):
    if not nvme0n1.supports(0xc):
        pytest.skip("verify command is not supported")

    pass


