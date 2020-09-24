#
#  BSD LICENSE
#
#  Copyright (c) Crane Chu <cranechu@gmail.com>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#    * Neither the name of Intel Corporation nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# -*- coding: utf-8 -*-


import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.zns import Zone


def test_zns_identify_namespace(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=1).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=5).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=6).waitdone()
    logging.info(buf.dump(64))
    

def test_zns_management_receive(nvme0n1, qpair, buf):
    zone_size = 0x8000
    nvme0n1.zns_mgmt_receive(qpair, buf).waitdone()
    nzones = buf.data(7, 0)
    logging.info("number of zones: %d" % nzones)

    for i in range(10):
        base = 64
        nvme0n1.zns_mgmt_receive(qpair, buf, slba=i*zone_size).waitdone()
        zone_type = buf.data(base)
        assert zone_type == 2

        zone = Zone(qpair, nvme0n1, i*zone_size)
        assert buf.data(base+1)>>4 == zone.state
        assert buf.data(base+15, base+8) == zone.capacity

        logging.info("zone %d, state 0x%x, attr 0x%x, zslba 0x%x, zcap 0x%x, wp 0x%x" %
                     (i, zone.state, zone.attributes, zone.slba,
                      zone.capacity, zone.wpointer))
    

def test_zns_management_send(nvme0n1, qpair):
    z0 = Zone(qpair, nvme0n1, 0)
    logging.info(z0.state)
    for a in [4, 3]:
        z0.action = a
        logging.info(z0.state)


@pytest.mark.parametrize("slba", [0, 0x8000, 0x10000, 0x80000, 0x100000])
def test_zns_state_machine(nvme0n1, qpair, slba):
    z0 = Zone(qpair, nvme0n1, slba)
    assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'
    
    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.finish()
    assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.reset()
    assert z0.state == 'Empty'

    z0.open()
    assert z0.state == 'Explicitly Opened'
    
    z0.close()
    assert z0.state == 'Closed'

    z0.reset()
    assert z0.state == 'Empty'
    
    z0.finish()
    assert z0.state == 'Full'
    

def test_zns_show_zone(nvme0n1, qpair, slba=0):
    z0 = Zone(qpair, nvme0n1, slba)
    logging.info(z0)

    
def test_zns_write(nvme0n1, qpair, slba=0):
    buf = Buffer(256*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    logging.info(z0)

    with pytest.warns(UserWarning, match="ERROR status: 01/b9"):
        z0.write(qpair, buf, 0, 256//4).waitdone()

    z0.reset()
    z0.open()
    for i in range(16):
        z0.write(qpair, buf, 0, 256//4)
    qpair.waitdone(16)
    logging.info(z0)
