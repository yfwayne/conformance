import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_features_fid_0(nvme0):
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.getfeatures(0).waitdone()

    
def test_features_sel_00(nvme0):
    orig_config = 0
    def getfeatures_cb_1(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    nvme0.getfeatures(1, sel=0, cb=getfeatures_cb_1).waitdone()

    nvme0.setfeatures(1, cdw11=orig_config|0x7).waitdone()

    new_config = 0
    def getfeatures_cb_2(cdw0, status):
        nonlocal new_config; new_config = cdw0
    nvme0.getfeatures(1, sel=0, cb=getfeatures_cb_2).waitdone()
    logging.debug("%x" % new_config)
    assert new_config == orig_config|0x7

    nvme0.setfeatures(1, cdw11=orig_config).waitdone()
    

def test_features_sel_01(nvme0, new_value=0x7):
    if not nvme0.id_data(521, 520)&0x10:
        pytest.skip("feature sv is not supported")

    orig_config = nvme0.getfeatures(1, sel=0).waitdone()
    logging.debug("%x" % orig_config)

    new_config = nvme0.getfeatures(1, sel=1).waitdone()
    logging.debug("%x" % new_config)
    assert orig_config == new_config

    nvme0.setfeatures(1, cdw11=orig_config|new_value).waitdone()

    new_config = nvme0.getfeatures(1, sel=0).waitdone()
    logging.debug("%x" % new_config)
    logging.debug("%x" % orig_config)
    assert new_config == orig_config|0x07
    new_config = nvme0.getfeatures(1, sel=1).waitdone()
    logging.debug("%x" % orig_config)
    assert new_config == orig_config

    nvme0.setfeatures(1, cdw11=orig_config).waitdone()


def test_features_sel_01_reserved_bits(nvme0):
    # some reserved bits are not 0
    test_features_sel_01(nvme0, new_value=0xf)

    
def test_features_sel_10(nvme0, fid=0x10):
    if not nvme0.id_data(521, 520)&0x10:
        pytest.skip("feature sv is not supported")

    nvme0.setfeatures(fid, cdw11=0x1600164).waitdone()
    
    orig_config = 0
    def getfeatures_cb_1(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    nvme0.getfeatures(fid, sel=0, cb=getfeatures_cb_1).waitdone()
    logging.info("%x" % orig_config)

    # change value with save bit
    nvme0.setfeatures(fid, sv=1, cdw11=orig_config-1).waitdone()

    new_config = 0
    def getfeatures_cb_2(cdw0, status):
        nonlocal new_config; new_config = cdw0
    nvme0.getfeatures(fid, sel=2, cb=getfeatures_cb_2).waitdone()
    logging.info("%x" % new_config)
    assert new_config == 0x1600163
    nvme0.getfeatures(fid, sel=0, cb=getfeatures_cb_2).waitdone()
    logging.info("%x" % new_config)
    assert new_config == 0x1600163

    # check the feature after reset event
    nvme0.reset()

    new_config = 0
    def getfeatures_cb_3(cdw0, status):
        nonlocal new_config; new_config = cdw0
    nvme0.getfeatures(fid, sel=2, cb=getfeatures_cb_3).waitdone()
    logging.info("%x" % new_config)
    assert new_config == 0x1600163
    nvme0.getfeatures(fid, sel=0, cb=getfeatures_cb_3).waitdone()
    logging.info("%x" % new_config)
    assert new_config == 0x1600163

    # revert to default
    orig_config = 0
    def getfeatures_cb_4(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    nvme0.getfeatures(fid, sel=1, cb=getfeatures_cb_4).waitdone()
    logging.info("%x" % orig_config)    
    nvme0.setfeatures(fid, cdw11=orig_config).waitdone()
    

def test_features_sel_11(nvme0):
    if not nvme0.id_data(521, 520)&0x10:
        pytest.skip("feature sv is not supported")

    orig_config = 0
    def getfeatures_cb_1(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    for fid in range(1, 10):
        nvme0.getfeatures(fid, sel=3, cb=getfeatures_cb_1).waitdone()
        logging.info("fid 0x%02x capability: 0x%02x" % (fid, orig_config))


def test_features_invalid_sel(nvme0):
    for f in list(range(1, 0x20)) + list(range(0x80, 0x85)):
        for s in range(4, 8):
            with pytest.warns(UserWarning, match="ERROR status: 00/02"):
                nvme0.getfeatures(fid=f, sel=s).waitdone()

    
def test_features_set_volatile_write_cache(nvme0):
    if not nvme0.id_data(525)&0x1:
        pytest.skip("volatile cache is not preset")

    def get_wce(nvme0):
        wce = 0
        def vwc_cb(cdw0, status):
            nonlocal wce
            wce = cdw0
        nvme0.getfeatures(6, cb=vwc_cb).waitdone()
        return wce

    orig_wce = get_wce(nvme0)
    nvme0.setfeatures(6, cdw11=1).waitdone()
    assert get_wce(nvme0) == 1
    nvme0.setfeatures(6, cdw11=0).waitdone()
    assert get_wce(nvme0) == 0
    nvme0.setfeatures(6, cdw11=orig_wce).waitdone()
    assert orig_wce == get_wce(nvme0)


def test_features_set_invalid_ncqr(nvme0):
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.setfeatures(7, cdw11=0xffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.setfeatures(7, cdw11=0xffff0000).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.setfeatures(7, cdw11=0xffffffff).waitdone()
