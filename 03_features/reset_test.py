import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


def test_reset(nvme0, subsystem, pcie):
    pcie.reset()
    nvme0.reset()
    subsystem.reset()
