import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_abort_aer_commands(nvme0, aer):
    # aer callback function
    def cb(cdw0, status):
        logging.info("in aer cb, status 0x%x" % status)
        assert ((status&0xfff)>>1) == 0x0007
    aer(cb)

    for i in range(100):
        nvme0.abort(i)

    logging.info("reap 104 command, including abort, and also aer commands")
    with pytest.warns(UserWarning, match="AER notification"):
        nvme0.waitdone(104)

