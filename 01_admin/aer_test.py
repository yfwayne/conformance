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
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_aer_limit_exceeded(nvme0):
    aerl = nvme0.id_data(259)+1
    logging.info(aerl)
    
    # another one is sent in defaul nvme init
    for i in range(aerl-1):
        nvme0.aer()

    # send one more
    with pytest.warns(UserWarning, match="ERROR status: 01/05"):
        nvme0.aer()
        nvme0.getfeatures(7).waitdone()

    # abort all
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        for i in range(100):
            nvme0.abort(127-i).waitdone()


def test_aer_sanitize(pcie, buf):
    # aer callback function
    aer_cdw0 = 0
    def aer_cb(cdw0, status):
        nonlocal aer_cdw0; aer_cdw0 = cdw0
        
    def nvme_init(nvme0):
        # 2. disable cc.en and wait csts.rdy to 0
        nvme0[0x14] = 0
        while not (nvme0[0x1c]&0x1) == 0: pass

        # 3. set admin queue registers
        nvme0.init_adminq()

        # 4. set register cc
        nvme0[0x14] = 0x00460000

        # 5. enable cc.en
        nvme0[0x14] = 0x00460001

        # 6. wait csts.rdy to 1
        while not (nvme0[0x1c]&0x1) == 1: pass

        # 7. identify controller
        nvme0.identify(Buffer(4096)).waitdone()

        # 8. create and identify all namespace
        nvme0.init_ns()

        # 9. set/get num of queues
        nvme0.setfeatures(0x7, cdw11=0x00ff00ff).waitdone()
        nvme0.getfeatures(0x7).waitdone()

        # 10. send out all aer
        aerl = nvme0.id_data(259)+1
        for i in range(aerl):
            nvme0.aer(cb=aer_cb)

    nvme0 = Controller(pcie, nvme_init_func=nvme_init)
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

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1
        
    # test sanitize once more with new aer
    nvme0.sanitize().waitdone()  # sanitize command is completed
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
    assert aer_cdw0 == 0x810106


def test_aer_mask_event(nvme0):
    orig_config_b = nvme0.getfeatures(0xb).waitdone()
    
    # disable the SMART/health event
    nvme0.setfeatures(0xb, cdw11=orig_config_b&~2).waitdone()
    config = nvme0.getfeatures(0xb).waitdone()
    assert not config&2

    # set temperature to generate event
    smart_log = Buffer()
    
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    ktemp = smart_log.data(2, 1)
    from pytemperature import k2c
    logging.info("temperature: %0.2f degreeC" % k2c(ktemp))

    # over composite temperature threshold
    orig_config_4 = nvme0.getfeatures(4).waitdone()
    nvme0.setfeatures(4, cdw11=ktemp-10).waitdone()

    # AER should not be triggered here
    nvme0.getlogpage(0x02, smart_log, 512).waitdone()
    logging.info(smart_log.data(0))
    assert smart_log.data(0) & 0x2
    
    # revert to default
    nvme0.setfeatures(4, cdw11=orig_config_4).waitdone()
    nvme0.setfeatures(0xb, cdw11=orig_config_b).waitdone()
    
