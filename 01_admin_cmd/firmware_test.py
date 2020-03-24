import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


@pytest.mark.parametrize("size", [4096, 10, 4096*2])
@pytest.mark.parametrize("offset", [4096, 10, 4096*2])
def test_firmware_download(nvme0, size, offset):
    buf = Buffer(size)
    with pytest.warns(UserWarning, match="ERROR status: 01/14"):
        nvme0.fw_download(buf, offset).waitdone()


def test_firmware_commit(nvme0):
    buf = Buffer(4096*16)
    nvme0.fw_download(buf, 0).waitdone()
    
    logging.info("commit without valid firmware image")
    with pytest.warns(UserWarning, match="ERROR status: 01/07"):
        nvme0.fw_commit(1, 0).waitdone()

    logging.info("commit to invalid firmware slot")
    with pytest.warns(UserWarning, match="ERROR status: 01/06"):
        nvme0.fw_commit(7, 2).waitdone()

