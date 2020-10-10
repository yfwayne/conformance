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
import random
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem, __version__
from scripts.zns import Zone


# LBA Format Extension Data Structure
# Zone Descriptor Extension Size bit 71:64 (ZDES)
# Zone Size 63:0 (ZSZE)
def get_zone_desctr_size(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=5, csi=2).waitdone()
    zone_desctr_size = buf.data(3833, 3832)
    return zone_desctr_size


def get_zone_size(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=5, csi=2).waitdone()
    zone_size = buf.data(3831, 3824)
    if zone_size == 0:
        zone_size = 0x8000
    return zone_size


def get_num_of_zones(nvme0n1, qpair, buf):
    nvme0n1.zns_mgmt_receive(qpair, buf).waitdone()
    nzones = buf.data(7, 0)
    return nzones


def get_zns_size(nvme0, nvme0n1, qpair, buf):
    nzones = get_num_of_zones(nvme0n1, qpair, buf)
    zone_size = get_zone_size(nvme0, buf)
    return (nzones * zone_size)


def get_cap_css(nvme0):
    css = ((nvme0.cap >> 32) & 0x1FE0) >> 5
    logging.debug("CAP.CSS= 0x%x" % css)
    return css


def get_zslba_list(nvme0, nvme0n1, qpair, buf):
    zone_size = get_zone_size(nvme0, buf)
    zns_size = get_zns_size(nvme0, nvme0n1, qpair, buf)
    logging.info("zone size:0x%x, Total:0x%x" %(zone_size, zns_size))
    return list(range(0, zns_size, zone_size))


def test_reset_all_zones(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    zone_size = get_zone_size(nvme0, buf)
    zns_size = get_zns_size(nvme0, nvme0n1, qpair, buf)
    for slba in range(0, zns_size, zone_size):
        logging.info("Reset zone @zslba: 0x%x" % slba)
        zone = Zone(qpair, nvme0n1, slba)
        zone.reset()

    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)


@pytest.fixture(scope="session")
def buf():
    ret = Buffer(96*1024, "pynvme zns buffer")
    yield ret
    del ret


#@pytest.fixture()
#def nvme0n1(nvme0):
    # only verify data in zone 0
    # ret = Namespace(nvme0, 1, 0x8000)
#    ret = Namespace(nvme0)
#    yield ret
#    ret.close()


@pytest.fixture()
def zone(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    zone_size = get_zone_size(nvme0, buf)
    slba = zone_size*int(random.random()*100)
    ret = Zone(qpair, nvme0n1, slba)
    if ret.state == 'Full':
        ret.reset()
    if ret.state == 'Empty':
        ret.open()
    assert ret.state == 'Explicitly Opened'
    assert ret.wpointer == ret.slba
    return ret


def test_dut_firmware_and_model_name(nvme0):
    logging.info(nvme0.id_data(63, 24, str))
    logging.info(nvme0.id_data(71, 64, str))
    logging.info("testing conformance with pynvme " + __version__)

    
def test_zns_identify_namespace(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=1).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=5).waitdone()
    logging.info(buf.dump(64))
    nvme0.identify(buf, nsid=1, cns=6).waitdone()
    logging.info(buf.dump(64))
    

def test_zns_management_receive(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")
    
    zone_size = get_zone_size(nvme0, buf)
    nvme0n1.zns_mgmt_receive(qpair, buf).waitdone()
    nzones = buf.data(7, 0)
    logging.info("number of zones: %d" % nzones)
    logging.info("zone size: 0x%x" % zone_size)

    for i in range(nzones):
        base = 64
        nvme0n1.zns_mgmt_receive(qpair, buf, slba=i*zone_size).waitdone()
        zone_type = buf.data(base)
        assert zone_type == 2

        zone = Zone(qpair, nvme0n1, i*zone_size)
        assert zone.capacity <= zone_size
        #assert buf.data(base+1)>>4 == 14
        assert buf.data(base+15, base+8) == zone.capacity
        logging.info(zone)
    

def test_zns_management_send(nvme0, nvme0n1, qpair):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    z0 = Zone(qpair, nvme0n1, 0)
    z0.action(2)
    assert z0.state == 'Full'


@pytest.mark.parametrize("slba", [0, 0x8000, 0x10000, 0x18000, 0x38000])
#@pytest.mark.parametrize("slba", zslba_list)
def test_zns_state_machine(nvme0, nvme0n1, qpair, buf, slba):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    z0 = Zone(qpair, nvme0n1, slba)

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
    
    z0.finish()
    assert z0.state == 'Full'

    z0.reset()
    assert z0.state == 'Empty'
    

def test_zns_state_machine1(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    zslba = get_zslba_list(nvme0, nvme0n1, qpair, buf)    
    for slba in zslba:
        z0 = Zone(qpair, nvme0n1, slba)
        logging.info("zslba:0x%x" % slba)

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

        z0.reset()


def test_zns_show_zone(nvme0, nvme0n1, qpair, slba=0):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    z0 = Zone(qpair, nvme0n1, slba)
    logging.info(z0)

    
def test_zns_write_full_zone(nvme0, nvme0n1, qpair, slba=0):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    with pytest.warns(UserWarning, match="ERROR status: 01/"):
        z0.write(qpair, buf, 0, 24).waitdone()

    z0.reset()
    z0.finish()
    assert z0.state == 'Full'


def test_zns_fill_a_zone(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    nzones = get_num_of_zones(nvme0n1, qpair, buf)
    zone_size = get_zone_size(nvme0, buf)
    slba = zone_size*int(random.randrange(nzones))
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()

    for lba in range(slba, slba+zone_size, 8):
        nvme0n1.write(qpair, buf, lba, 8).waitdone()

    assert zone.state == 'Full'
    # reset_all_zones(nvme0, nvme0n1, qpair, buf)
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)


def test_zns_ioworker(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    nzones = get_num_of_zones(nvme0n1, qpair, buf)
    zone_size = get_zone_size(nvme0, buf)
    slba = zone_size*int(random.randrange(nzones))
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()    

    nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
            region_start=slba, region_end=slba+zone_size).start().close()

    assert zone.state == 'Full'
    # reset_all_zones(nvme0, nvme0n1, qpair, buf)
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)


def test_zns_transition_next_zone(nvme0, nvme0n1, qpair, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    nzones = get_num_of_zones(nvme0n1, qpair, buf)
    zone_size = get_zone_size(nvme0, buf)
    zone_index = int(random.randrange(nzones))
    next_index = (zone_index + 1) % nzones
    slba = zone_size * zone_index
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()
    next_zone = Zone(qpair, nvme0n1, next_index*zone_size)
    next_zone.reset()

    nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
            region_start=slba, region_end=slba+zone_size+128).start().close()

    assert zone.state == 'Full'
    assert next_zone.state == 'Implicitly Opened'
    # reset_all_zones(nvme0, nvme0n1, qpair, buf)
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)    
    

def test_zns_write_1(nvme0, nvme0n1, qpair, zone):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = Buffer(96*1024)
    zone.reset()
    zone.write(qpair, buf, 0x0, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'

    
def test_zns_write_2(nvme0, nvme0n1, qpair, zone):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 12)
    zone.write(qpair, buf, 12, 12)
    zone.close()
    zone.finish()
    qpair.waitdone(2)
    assert zone.state == 'Full'


def test_zns_write_192k(nvme0, nvme0n1, qpair, zone):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 24, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'

    
def test_zns_write_invalid_lba(nvme0, nvme0n1, qpair, zone):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")
        
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 24, 24).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/bc"):
        zone.write(qpair, buf, 24, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'


def test_zns_write_twice(nvme0, nvme0n1, qpair, zone):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")
    
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 0, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'    


def test_zns_write_to_full(nvme0, nvme0n1, qpair, zone, io_counter=768):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = [Buffer(96*1024)]*768
    for i in range(io_counter):
        buf[i][8] = i%256
        zone.write(qpair, buf[i], i*24, 24)
    qpair.waitdone(io_counter)
    #assert zone.state == 'Full'
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)
    
        
@pytest.mark.parametrize("io_counter", [1, 2, 10, 39, 100, 255])
def test_zns_write_and_read_multiple(nvme0, nvme0n1, qpair, zone, io_counter,buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf_list = [Buffer(96*1024) for i in range(io_counter)]
    for i in range(io_counter):
        buf_list[i][8] = i
        zone.write(qpair, buf_list[i], i*24, 24)
    zone.close()
    zone.finish()
    qpair.waitdone(io_counter)
    #assert zone.state == 'Full'
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf)
    
    for i in range(io_counter):
        buf = Buffer(96*1024)
        zone.read(qpair, buf, i*24, 24).waitdone()
        logging.debug(buf.dump(16))
        assert buf[8] == i
        

def _test_zns_ioworker_baisc(zone):
    assert zone.state == 'Explicitly Opened'
    r = zone.ioworker(io_size=24, io_count=768, qdepth=16).close()
    logging.info(r)
    assert zone.state == 'Full'
    
    
def test_zns_hello_world_2(nvme0, nvme0n1, qpair, zone, buf):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")
        
    buf[10:21] = b'hello world'
    zone.write(qpair, buf, 0, 24)
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'    
    
    read_buf = Buffer()
    read_qpair = Qpair(nvme0, 10)
    zone.read(read_qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'
        
    
@pytest.mark.parametrize("repeat", range(30)) #100
def test_zns_write_explicitly_open(nvme0, nvme0n1, qpair, buf, zone, repeat):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")
        
    z0 = zone
    slba = z0.slba
    assert z0.state == 'Explicitly Opened'
    assert z0.wpointer == slba

    z0.write(qpair, buf, 0, 96//4)
    time.sleep(1)
    assert z0.state == 'Explicitly Opened'
    assert z0.wpointer == slba+0x18

    z0.close()
    #logging.info(z0)
    assert z0.state == 'Closed'
    assert z0.wpointer == slba+0x18
    
    z0.finish()
    qpair.waitdone()
    logging.info(z0)
    assert z0.state == 'Full'
    assert z0.wpointer == slba+0x4800


@pytest.mark.parametrize("repeat", range(10)) #100
@pytest.mark.parametrize("slba", [0, 0x8000, 0x38000])
def test_zns_write_implicitly_open(nvme0, nvme0n1, qpair, slba, repeat):
    css = get_cap_css(nvme0)
    if not (css & 0x40):
        pytest.skip("zns is not supported")

    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    #assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'
    assert z0.wpointer == slba

    z0.write(qpair, buf, 0, 96//4)
    time.sleep(1)
    assert z0.state == 'Implicitly Opened'
    assert z0.wpointer == slba+0x18

    z0.close()
    #logging.info(z0)
    assert z0.state == 'Closed'
    assert z0.wpointer == slba+0x18
    
    z0.finish()
    qpair.waitdone()
    logging.info(z0)
    assert z0.state == 'Full'
    assert z0.wpointer == slba+0x4800


