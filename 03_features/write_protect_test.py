import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_write_protect(nvme0, nvme0n1, buf, verify):
    if not nvme0.id_data(531):
        pytest.skip("wirte protect is not supported")

    pass
