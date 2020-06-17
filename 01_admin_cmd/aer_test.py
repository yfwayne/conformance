import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_aer_limit_exceeded(nvme0):
    aerl = nvme0.id_data(259)+1
    logging.info(aerl)
    
    def aer_cb(cdw0, status):
        assert ((status&0xfff)>>1) == 0x0007
    # another one is sent in defaul nvme init
    for i in range(aerl-1):
        nvme0.aer(cb=aer_cb)

    # send one more
    with pytest.warns(UserWarning, match="ERROR status: 01/05"):
        nvme0.aer().waitdone()

    # abort all
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        for i in range(100):
            nvme0.abort(127-i).waitdone()
        nvme0.waitdone(aerl)


def test_aer_sanitize(nvme0, nvme0n1, buf):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  # sanitize command is completed

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1
        
    # aer callback function
    aer_cdw0 = 0
    def aer_cb(cdw0, status):
        nonlocal aer_cdw0; aer_cdw0 = cdw0
    nvme0.aer(cb=aer_cb)
        
    # test sanitize once more with new aer
    nvme0.sanitize().waitdone()  # sanitize command is completed
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()
    assert aer_cdw0 == 0x810106


def test_aer_mask_event(nvme0):
    config = nvme0.getfeatures(0xb).waitdone()
    assert config&1

    # disable the SMART/health event
    nvme0.setfeatures(0xb, cdw11=config&0xfffffffe).waitdone()
    config = nvme0.getfeatures(0xb).waitdone()
    assert not config&1

    # set temperature to generate event
    smart_log = Buffer()
    
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    ktemp = smart_log.data(2, 1)
    logging.info("temperature: %d degreeF" % ktemp)

    # over composite temperature threshold
    nvme0.setfeatures(4, cdw11=ktemp-10).waitdone()

    # AER should be triggered
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x02, smart_log, 512).waitdone()

    # AER is consumed
    nvme0.setfeatures(4, cdw11=ktemp-20).waitdone()
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()    
    assert smart_log.data(0) & 0x2
    
    # revert to default
    orig_config = nvme0.getfeatures(4, sel=1).waitdone()
    nvme0.setfeatures(4, cdw11=orig_config).waitdone()
    nvme0.setfeatures(0xb, cdw11=config).waitdone()
    
