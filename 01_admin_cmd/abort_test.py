import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_abort_aer_commands(nvme0):
    aerl = nvme0.id_data(259)+1
    logging.info(aerl)

    def aer_cb(cdw0, status):
        assert ((status&0xfff)>>1) == 0x0007
    # another one is sent in defaul nvme init
    for i in range(aerl-1):
        nvme0.aer(cb=aer_cb)

    # ASYNC LIMIT EXCEEDED (01/05)
    with pytest.warns(UserWarning, match="ERROR status: 01/05"):
        nvme0.aer().waitdone()

    # no timeout happen on aer
    time.sleep(15)

    # ABORTED - BY REQUEST (00/07)
    logging.info("reap %d command, including abort, and also aer commands" % (100+aerl))
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        for i in range(100):
            nvme0.abort(i).waitdone()
        nvme0.waitdone(aerl)
        
