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


import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_getlogpage_page_id(nvme0, buf):
    for lid in (1, 2, 3):
        nvme0.getlogpage(lid, buf).waitdone()

    for lid in (0, 0x6f, 0x7f):
        with pytest.warns(UserWarning, match="ERROR status: 01/09"):
            nvme0.getlogpage(lid, buf).waitdone()
        

@pytest.mark.parametrize("repeat", range(32))
def test_getlogpage_invalid_numd(nvme0, repeat):
    dts = nvme0.mdts//4 + 1 + repeat
    buf = Buffer(dts*4)

    for lid in (1, 2, 3):
        nvme0.getlogpage(lid, buf).waitdone()


def test_getlogpage_after_error(nvme0, nvme0n1, buf, qpair):
    nvme0.getlogpage(1, buf).waitdone()
    nerror = buf.data(7, 0)
    nvme0n1.write_uncorrectable(qpair, 0, 8).waitdone()

    # generate 2 errors
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, buf, 0, 8).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 02/81"):
        nvme0n1.read(qpair, buf, 0, 8).waitdone()

    time.sleep(1) # wait error information ready
    nvme0.getlogpage(1, buf).waitdone()
    nerror1 = buf.data(7, 0)
    nerror2 = buf.data(64+7, 64)
    assert nerror == nerror2-1
    assert nerror1 == nerror2+1

    nvme0n1.write(qpair, buf, 0, 8).waitdone()
    

@pytest.mark.parametrize("len", (1, 2, 4))
def test_getlogpage_data_unit_read(nvme0, nvme0n1, buf, qpair, len):
    if not nvme0n1.supports(5):
        pytest.skip("compare is not support")

    nvme0n1.write(qpair, buf, 0, len).waitdone()

    nvme0.getlogpage(2, buf).waitdone()
    nread1 = buf.data(47, 32)

    # read
    for i in range(1000):
        nvme0n1.read(qpair, buf, 0, len).waitdone()
    nvme0.getlogpage(2, buf).waitdone()
    nread2 = buf.data(47, 32)
    assert nread2 == nread1+len

    # compare
    nvme0n1.read(qpair, buf, 0, len).waitdone()  # get correct data
    for i in range(1000):
        nvme0n1.compare(qpair, buf, 0, len).waitdone()
    nvme0.getlogpage(2, buf).waitdone()
    nread3 = buf.data(47, 32)
    assert nread3 == nread2+len

    # verify
    if nvme0n1.supports(0xc):
        for i in range(1000):
            nvme0n1.verify(qpair, 0, len).waitdone()
        nvme0.getlogpage(2, buf).waitdone()
        nread4 = buf.data(47, 32)
        assert nread4 == nread3+len    


@pytest.mark.parametrize("len", (1, 2, 4))
def test_getlogpage_data_unit_write(nvme0, nvme0n1, len, buf, qpair):
    if not nvme0n1.supports(5):
        pytest.skip("compare is not support")

    nvme0n1.write(qpair, buf, 0).waitdone()

    nvme0.getlogpage(2, buf).waitdone()
    nwrite1 = buf.data(63, 48)

    for i in range(1000):
        nvme0n1.write(qpair, buf, 0, len).waitdone()

    nvme0.getlogpage(2, buf).waitdone()
    nwrite2 = buf.data(63, 48)
    assert nwrite2 == nwrite1+len
    
    for i in range(1000):
        nvme0n1.write_uncorrectable(qpair, 0, len).waitdone()

    nvme0.getlogpage(2, buf).waitdone()
    nwrite3 = buf.data(63, 48)
    assert nwrite3 == nwrite2

    nvme0n1.write(qpair, Buffer(4096), 0, 8).waitdone()
    

@pytest.mark.skip(reason="subsystem")
def test_getlogpage_power_cycle_count(nvme0, subsystem, buf):
    def get_power_cycles(nvme0):
        nvme0.getlogpage(2, buf, 512).waitdone()
        return buf.data(115, 112)

    powercycle = get_power_cycles(nvme0)
    subsystem.poweroff()
    subsystem.poweron()
    nvme0.reset()
    assert get_power_cycles(nvme0) == powercycle+1


def test_getlogpage_namespace(nvme0, buf):
    nvme0.getlogpage(2, buf, nsid=1).waitdone()
    nvme0.getlogpage(2, buf, nsid=0xffffffff).waitdone()

    # getlogpage for id=2 nsid can be 0 or 0xffffffff
    nvme0.getlogpage(2, buf, nsid=0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.getlogpage(2, buf, nsid=2).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.getlogpage(2, buf, nsid=0xfffffffe).waitdone()

        
def test_getlogpage_smart_composite_temperature(nvme0):
    smart_log = Buffer()
    
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    ktemp = smart_log.data(2, 1)
    logging.debug("temperature: %d degreeF" % ktemp)

    # warning with AER
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        # over composite temperature threshold
        nvme0.setfeatures(4, cdw11=ktemp-10).waitdone()
        
        nvme0.getlogpage(0x02, smart_log, 512).waitdone()
        logging.debug("0x%x" % smart_log.data(0))
        nvme0.getlogpage(0x02, smart_log, 512).waitdone()    
        assert smart_log.data(0) & 0x2

        # higher threshold
        nvme0.setfeatures(4, cdw11=ktemp+10).waitdone()

    # aer is not expected
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    ktemp = smart_log.data(2, 1)
    logging.debug("temperature: %d degreeF" % ktemp)

    # revert to default
    orig_config = 0
    def getfeatures_cb_4(cdw0, status):
        nonlocal orig_config; orig_config = cdw0
    nvme0.getfeatures(4, sel=1, cb=getfeatures_cb_4).waitdone()
    nvme0.setfeatures(4, cdw11=orig_config).waitdone()    

    
def test_getlogpage_persistent_event_log(nvme0):
    if not (nvme0.id_data(261)&0x10):
        pytest.skip("feature sv is not supported")


def test_getlogpage_firmware_slot_info_nsid_1(nvme0, buf):
    """For Log Pages with a scope of NVM subsystem or controller (as shown in Figure 191 and Figure 192), the
controller should abort commands that specify namespace identifiers other than 0h or FFFFFFFFh with
status Invalid Field in Command."""

    nvme0.getlogpage(3, buf, 512, nsid=0).waitdone()
    nvme0.getlogpage(3, buf, 512, nsid=0xffffffff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.getlogpage(3, buf, 512, nsid=1).waitdone()
