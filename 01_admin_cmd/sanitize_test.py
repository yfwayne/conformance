import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_sanitize_operations_basic(nvme0, nvme0n1, buf):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  # sanitize command is completed

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
            nvme0.getlogpage(0x81, buf, 20).waitdone()
            time.sleep(1)    
