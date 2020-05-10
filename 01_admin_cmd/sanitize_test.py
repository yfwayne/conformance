import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_sanitize_operations_basic(nvme0, nvme0n1, buf, subsystem):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    # prepare one aer
    def aer_cb(cdw0, status1):
        logging.warning("AER triggered, dword0: 0x%x, status1: 0x%x" %
                        (cdw0, status1))
        warnings.warn("AER notification is triggered")

    # start sanitize, and wait it complete
    logging.info("supported sanitize operation: %d" % buf.data(331, 328))
    nvme0.sanitize().waitdone()
    nvme0.aer(cb=aer_cb)

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)

        # aer should happen after sanitize done
        nvme0.waitdone()

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1


def test_sanitize_operations_powercycle(nvme0, nvme0n1, buf, subsystem):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    # start sanitize, and wait it complete
    logging.info("supported sanitize operation: %d" % buf.data(331, 328))
    nvme0.sanitize().waitdone()

    time.sleep(1)
    subsystem.power_cycle()
    nvme0.reset()

    # check sanitize status in log page
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
        time.sleep(1)
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        progress = buf.data(1, 0)*100//0xffff
        logging.info("%d%%" % progress)

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1


