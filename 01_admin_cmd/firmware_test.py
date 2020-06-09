import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


@pytest.mark.parametrize("size", [4096, 10, 4096*2])
@pytest.mark.parametrize("offset", [4096, 10, 4096*2])
def test_firmware_download(nvme0, size, offset):
    fwug = nvme0.id_data(319)
    if fwug == 0 or fwug == 0xff:
        pytest.skip("not applicable")
    
    buf = Buffer(size)
    with pytest.warns(UserWarning, match="ERROR status: 01/14"):
        nvme0.fw_download(buf, offset).waitdone()


def test_firmware_commit(nvme0):
    frmw = nvme0.id_data(260)
    slot1_ro = frmw&1
    slot_count = (frmw>>1)&7
    logging.info(slot1_ro)
    logging.info(slot_count)
    
    buf = Buffer(4096*16)
    nvme0.fw_download(buf, 0).waitdone()

    logging.info("commit with an invalid firmware image")
    for slot in range(1, slot_count+1):
        with pytest.warns(UserWarning, match="ERROR status: 01/07"):
            nvme0.fw_commit(slot, 0).waitdone()
        
    logging.info("commit to invalid firmware slot")
    with pytest.warns(UserWarning, match="ERROR status: 01/07"):
        nvme0.fw_commit(0, 0).waitdone()

    if slot_count == 7:
        pytest.skip("no invalid slot")

    for slot in range(slot_count+1, 8):
        with pytest.warns(UserWarning, match="ERROR status: 01/06"):
            nvme0.fw_commit(slot, 2).waitdone()

