# Copyright (C) 2020 Crane Chu <cranechu@gmail.com>
# This file is part of pynvme's conformance test
#
# pynvme's conformance test is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# pynvme's conformance test is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pynvme's conformance test. If not, see
# <http://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-


import pytest
import logging
import random
from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_features_fid_0(nvme0):
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.getfeatures(0).waitdone()

    
def test_features_sel_00(nvme0):
    orig_config = nvme0.getfeatures(4, sel=0).waitdone()
    nvme0.setfeatures(4, cdw11=orig_config+7).waitdone()
    new_config = nvme0.getfeatures(4, sel=0).waitdone()
    assert new_config == orig_config+7
    nvme0.setfeatures(4, cdw11=orig_config).waitdone()
    

def test_features_sel_01(nvme0, add_value=10):
    if not nvme0.id_data(521, 520)&0x10:
        pytest.skip("feature sv is not supported")

    orig_config = nvme0.getfeatures(4, sel=0).waitdone()
    new_config = nvme0.getfeatures(4, sel=1).waitdone()
    assert orig_config == new_config

    nvme0.setfeatures(4, cdw11=orig_config+add_value).waitdone()
    new_config = nvme0.getfeatures(4, sel=0).waitdone()
    logging.info(orig_config)
    logging.info(new_config)
    assert new_config == orig_config+add_value
    
    new_config = nvme0.getfeatures(4, sel=1).waitdone()
    assert new_config == orig_config

    nvme0.setfeatures(4, cdw11=orig_config).waitdone()


@pytest.mark.xfail(reason="cannot write reserved bit")
def test_features_sel_01_reserved_bit(nvme0):
    test_features_sel_01(nvme0, add_value=10+(1<<1))
    # write a reserved bit
    test_features_sel_01(nvme0, add_value=10+(1<<31))

    
def test_features_sel_10(nvme0, fid=0x10):
    if not nvme0.id_data(521, 520)&0x10:
        pytest.skip("feature sv is not supported")

    # Get random HCTM value
    while(1):
        MNTMT = nvme0.id_data(325, 324)
        MXTMT = nvme0.id_data(327, 326)
        assert MNTMT != MXTMT
        randomTMT1 = random.randrange(MNTMT, MXTMT)
        randomTMT2 = random.randrange(MNTMT, MXTMT)
        if randomTMT1 != randomTMT2:
            break
        else:
            continue
        
    if randomTMT1 < randomTMT2:
        TMT1 = randomTMT1 << 16
        TMT2 = randomTMT2
    else:
        TMT1 = randomTMT2 << 16
        TMT2 = randomTMT1
    HCTM = TMT1 + TMT2
    
    nvme0.setfeatures(fid, cdw11=HCTM).waitdone()
    
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
    assert new_config == HCTM-1
    nvme0.getfeatures(fid, sel=0, cb=getfeatures_cb_2).waitdone()
    logging.info("%x" % new_config)
    assert new_config == HCTM-1

    # check the feature after reset event
    nvme0.reset()

    new_config = 0
    def getfeatures_cb_3(cdw0, status):
        nonlocal new_config; new_config = cdw0
    nvme0.getfeatures(fid, sel=2, cb=getfeatures_cb_3).waitdone()
    logging.info("%x" % new_config)
    assert new_config == HCTM-1
    nvme0.getfeatures(fid, sel=0, cb=getfeatures_cb_3).waitdone()
    logging.info("%x" % new_config)
    assert new_config == HCTM-1

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
