import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_abort_aer_commands(nvme0):
    # aer callback function
    def cb(cdw0, status):
        logging.info("in aer cb, status 0x%x" % status)
        warnings.warn("AER notification is triggered")
        assert ((status&0xfff)>>1) == 0x0007

    aerl = nvme0.id_data(259)+1
    for i in range(aerl):
        nvme0.aer(cb)
    
    for i in range(100):
        nvme0.abort(i)

    logging.info("reap %d command, including abort, and also aer commands" % (100+aerl))
    with pytest.warns(UserWarning, match="AER notification"):
        nvme0.waitdone(100+aerl)

