import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_aer_limit_exceeded(nvme0):
    # aer should all sent by driver at init time
    with pytest.warns(UserWarning, match="ERROR status: 01/05"):
        nvme0.aer().waitdone()


@pytest.mark.parametrize("repeat", range(2))
def test_aer_sanitize(nvme0, nvme0n1, buf, aer, repeat):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    # aer callback function
    aer_cdw0 = 0
    def cb(cdw0, status):
        nonlocal aer_cdw0; aer_cdw0 = cdw0
        logging.info("sanitize AER, cdw0 0x%x" % cdw0)
    aer(cb)
        
    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  # sanitize command is completed

    # check sanitize status in log page
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            nvme0.getlogpage(0x81, buf, 20).waitdone()
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
            time.sleep(1)
            
    assert aer_cdw0 == 0x810106
            
    nvme0.reset()


def test_aer_mask_event(nvme0):
    config = 0
    def getfeatures_cb_1(cdw0, status):
        nonlocal config; config = cdw0
    nvme0.getfeatures(0xb, cb=getfeatures_cb_1).waitdone()
    logging.debug("%x" % config)
    assert config&1

    # disable the SMART/health event
    nvme0.setfeatures(0xb, cdw11=config&0xfffffffe).waitdone()
    nvme0.getfeatures(0xb, cb=getfeatures_cb_1).waitdone()
    logging.debug("%x" % config)
    assert not config&1

    # set temperature to generate event
    smart_log = Buffer()
    
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    ktemp = smart_log.data(2, 1)
    logging.debug("temperature: %d degreeF" % ktemp)

    # over composite temperature threshold
    nvme0.setfeatures(4, cdw11=ktemp-10).waitdone()

    # AER should be disabled
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    logging.debug("0x%x" % smart_log.data(0))
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()    
    assert smart_log.data(0) & 0x2
    
    # revert to default
    orig_config = 0
    def getfeatures_cb_4(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    nvme0.getfeatures(4, sel=1, cb=getfeatures_cb_4).waitdone()
    nvme0.setfeatures(4, cdw11=orig_config).waitdone()

    nvme0.setfeatures(0xb, cdw11=config).waitdone()
    
