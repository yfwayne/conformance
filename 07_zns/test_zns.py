#
#  BSD LICENSE
#
#  Copyright (c) Crane Chu <cranechu@gmail.com>
#  Copyright (c) Wayne Gao <yfwayne@hotmail.com>
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


skip_zns = True # False
pytestmark = pytest.mark.skipif(skip_zns, reason="zns is not supported")


def test_zns_support(nvme0):
    cap_css = ((nvme0.cap >> 32) & 0x1FE0) >> 5
    logging.info("CAP.CSS= 0x%x" % cap_css)


#TODO: Use identify data to skip automaticlly if non-zns drive
#pytestmark = pytest.mark.skipif(zns_not_supported(nvme0), reason="zns is not supported")  


# LBA Format Extension Data Structure
# Zone Descriptor Extension Size bit 71:64 (ZDES)
# Zone Size 63:0 (ZSZE)
@pytest.fixture( )
def zone_desctr_size(nvme0, buf):
    nvme0.identify(buf, nsid=1, cns=5, csi=2).waitdone()
    ret = buf.data(2832, 2832)
    logging.debug("ZDES: 0x%x" % ret) 
    return ret


@pytest.fixture( )
def zone_size(nvme0, buf):
    nvme0.identify(buf, nsid=1, cns=5, csi=2).waitdone()
    ret = buf.data(2831, 2816)
    logging.debug("zone size: 0x%x" % ret)
    if ret == 0:
        ret = 0x8000
    return ret


@pytest.fixture( )
def num_of_zones(nvme0n1, qpair, buf):
    nvme0n1.zns_mgmt_receive(qpair, buf).waitdone()
    ret = buf.data(7, 0)
    return ret


@pytest.fixture( )
def zns_size(num_of_zones, zone_size):
    ret = num_of_zones * zone_size
    return ret


@pytest.fixture( )
def zslba_list(zone_size, zns_size):
    logging.debug("zone size:0x%x, Total:0x%x" %(zone_size, zns_size))
    return list(range(0, zns_size, zone_size))


@pytest.fixture(scope="session")
def buf():
    ret = Buffer(96*1024, "pynvme zns buffer")
    yield ret
    del ret


@pytest.fixture()
def zone(nvme0, nvme0n1, qpair, buf, num_of_zones, zone_size):
    slba = zone_size*int(random.randrange(num_of_zones))
    logging.debug("slba:0x%x" % slba )
    ret = Zone(qpair, nvme0n1, slba)
    ret.reset()
    ret.open()
    assert ret.state == 'Explicitly Opened'
    assert ret.wpointer == ret.slba
    return ret


def get_zone_gap(nvme0n1, qpair, zone_size, slba):
    zone = Zone(qpair, nvme0n1, slba)
    ret = zone_size - zone.capacity
    logging.debug("zone size:0x%x, zcap:0x%x" %(zone_size, zone.capacity))
    return ret 


def test_reset_all_zones(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones, zns_size):
    for slba in range(0, zns_size, zone_size):
        logging.info("Reset zone @zslba: 0x%x" % slba)
        zone = Zone(qpair, nvme0n1, slba)
        zone.reset()

    test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)


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
    

def test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones):
    logging.info("number of zones: %d" % num_of_zones)
    logging.info("zone size: 0x%x" % zone_size)

    for i in range(num_of_zones):
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
    z0 = Zone(qpair, nvme0n1, 0)
    z0.action(2)
    assert z0.state == 'Full'


@pytest.mark.parametrize("slba", [0, 0x8000, 0x10000, 0x18000, 0x38000])
#@pytest.mark.parametrize("slba", zslba_list)
def test_zns_state_machine(nvme0, nvme0n1, qpair, buf, slba):
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
    

def test_zns_state_machine_all(nvme0, nvme0n1, qpair, buf, zslba_list):
    for slba in zslba_list:
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
    z0 = Zone(qpair, nvme0n1, slba)
    logging.info(z0)

    
def test_zns_write_full_zone(nvme0, nvme0n1, qpair, slba=0):
    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    #with pytest.warns(UserWarning, match="ERROR status: 01/"):
    z0.write(qpair, buf, 0, 16).waitdone()

    z0.reset()
    z0.finish()
    assert z0.state == 'Full'


def test_zns_fill_a_zone(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones):
    slba = zone_size*int(random.randrange(num_of_zones))
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()

    #for lba in range(slba, slba+zone_size, 8):
    #    nvme0n1.write(qpair, buf, lba, 8).waitdone()
    for lba in range(0, zone.capacity, 16):
        zone.write(qpair, buf, lba, 16).waitdone()

    assert zone.state == 'Full'
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)


def test_zns_ioworker(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones):
    slba = zone_size*int(random.randrange(num_of_zones))
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()    

    nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
            region_start=slba, region_end=slba+zone.capacity).start().close()

    assert zone.state == 'Full'
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)


@pytest.mark.parametrize("repeat", range(2))
def test_zns_transition_next_zone(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones, repeat):
    zone_index = int(random.randrange(num_of_zones))
    if zone_index == num_of_zones - 1:        
        next_index = zone_index
        zone_index = zone_index - 1
    else:
        next_index = (zone_index + 1) % num_of_zones
    slba = zone_size * zone_index
    next_slba = next_index*zone_size
    logging.info("Fill Zone 0x%x, zslba: 0x%x" % (zone_index, slba))
    logging.info("Next Zone 0x%x, zslba: 0x%x" % (next_index, next_slba))
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()
    next_zone = Zone(qpair, nvme0n1, next_slba)
    next_zone.reset()
    
    if (zone.capacity < zone_size):
        nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
                region_start=slba, region_end=slba+zone.capacity).start().close()
        nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
                region_start=next_slba, region_end=next_slba+128).start().close()
    else:
        nvme0n1.ioworker(io_size=8, lba_random=False, read_percentage=0, \
                region_start=slba, region_end=slba+zone.capacity+128).start().close()

    assert zone.state == 'Full'
    assert next_zone.state == 'Implicitly Opened'
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)
    

def test_zns_write_1(nvme0, nvme0n1, qpair, zone, buf):
    #buf = Buffer(96*1024)
    zone.reset()
    zone.write(qpair, buf, 0x0, 8).waitdone()
    zone.close()
    zone.finish()
    assert zone.state == 'Full'


def test_zns_write_a_full_zone(nvme0, nvme0n1, qpair, zone, buf):
    test_zns_write_1(nvme0, nvme0n1, qpair, zone, buf)
    
    with pytest.warns(UserWarning, match="ERROR status: 01/b9"):
        zone.write(qpair, buf, 0x0, 8).waitdone()


def test_zns_write_a_closed_zone(nvme0, nvme0n1, qpair, zone, buf, zone_size, num_of_zones):
    slba = zone_size*int(random.randrange(num_of_zones))
    logging.info("Test zslba: 0x%x" % slba)
    zone = Zone(qpair, nvme0n1, slba)
    zone.reset()

    zone.write(qpair, buf, 0, 16).waitdone()
    zone.close()

    with pytest.warns(UserWarning, match="ERROR status: 01/bc"):
        zone.write(qpair, buf, 0x0, 8).waitdone()
    test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)


def test_zns_write_2(nvme0, nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 12)
    zone.write(qpair, buf, 12, 12)
    zone.close()
    zone.finish()
    qpair.waitdone(2)
    assert zone.state == 'Full'


def test_zns_write_192k(nvme0, nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24)
    zone.write(qpair, buf, 24, 24).waitdone()
    zone.close()
    zone.finish()
    qpair.waitdone(1)
    assert zone.state == 'Full'

    
def test_zns_write_invalid_lba(nvme0, nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24).waitdone()
    zone.write(qpair, buf, 24, 24).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/bc"):
        zone.write(qpair, buf, 24, 24).waitdone()
    zone.close()
    zone.finish()
    assert zone.state == 'Full'


def test_zns_write_twice(nvme0, nvme0n1, qpair, zone):
    buf = Buffer(96*1024)
    zone.write(qpair, buf, 0, 24).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/bc"):
        zone.write(qpair, buf, 0, 24).waitdone()
    zone.close()
    zone.finish()
    assert zone.state == 'Full'    


def test_zns_write_to_full(nvme0, nvme0n1, qpair, zone, io_counter=768):
    buf = [Buffer(96*1024)]*768
    for i in range(io_counter):
        buf[i][8] = i%256
        zone.write(qpair, buf[i], i*16, 16)
    qpair.waitdone(io_counter)
    #assert zone.state == 'Full'
    #test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)
    
        
@pytest.mark.parametrize("io_counter", [1, 2, 10, 39, 100, 255])
def test_zns_write_and_read_multiple(nvme0, nvme0n1, qpair, zone, io_counter,buf):
    buf_list = [Buffer(96*1024) for i in range(io_counter)]
    for i in range(io_counter):
        buf_list[i][8] = i
        zone.write(qpair, buf_list[i], i*16, 16).waitdone()
    zone.close()
    zone.finish()
    assert zone.state == 'Full'
    
    for i in range(io_counter):
        buf = Buffer(96*1024)
        zone.read(qpair, buf, i*16, 16).waitdone()
        logging.debug(buf.dump(16))
        assert buf[8] == i
        

def test_zns_ioworker_baisc(zone, zone_size):
    assert zone.state == 'Explicitly Opened'
    r = zone.ioworker(io_size=16, io_count=zone_size/16, qdepth=16).start().close()
    logging.info(r)
    assert zone.state == 'Full'
    
    
def test_zns_hello_world_2(nvme0, nvme0n1, qpair, zone, buf):
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
        
    
@pytest.mark.parametrize("repeat", range(3)) #100
def test_zns_write_explicitly_open(nvme0, nvme0n1, qpair, buf, zone, repeat):
    z0 = zone
    slba = z0.slba
    assert z0.state == 'Explicitly Opened'
    assert z0.wpointer == slba

    z0.write(qpair, buf, 0, 16).waitdone()
    time.sleep(1)
    assert z0.state == 'Explicitly Opened'
    assert z0.wpointer == slba+0x10

    z0.close()
    #logging.info(z0)
    assert z0.state == 'Closed'
    assert z0.wpointer == slba+0x10
    
    z0.finish()
    logging.info(z0)
    assert z0.state == 'Full'
    assert z0.wpointer == slba+0x10


@pytest.mark.parametrize("repeat", range(10)) #100
@pytest.mark.parametrize("slba", [0, 0x8000, 0x38000])
def test_zns_write_implicitly_open(nvme0, nvme0n1, qpair, slba, repeat):
    buf = Buffer(96*1024)
    z0 = Zone(qpair, nvme0n1, slba)
    #assert z0.state == 'Full'
    
    z0.reset()
    assert z0.state == 'Empty'
    assert z0.wpointer == slba

    z0.write(qpair, buf, 0, 16).waitdone()
    time.sleep(1)
    logging.info("Write pointer:0x%x" % z0.wpointer)
    assert z0.state == 'Implicitly Opened'
    assert z0.wpointer == slba+16

    z0.close()
    #logging.info(z0)
    assert z0.state == 'Closed'
    assert z0.wpointer == slba+0x10
    
    z0.finish()
    logging.info(z0)
    assert z0.state == 'Full'
    assert z0.wpointer == slba+0x10


def test_write_append(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones):
    zone_index = int(random.randrange(num_of_zones))
    slba = zone_size * zone_index
    zone = Zone(qpair, nvme0n1, slba)
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))
    zone.reset()
    nvme0n1.send_cmd(0x7d, qpair, buf, 1, slba&0xffffffff, slba>>32).waitdone()
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))
    nvme0n1.send_cmd(0x7d, qpair, buf, 1, slba&0xffffffff, slba>>32).waitdone()
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))
    # zone append not from the zslba,Invalid Field in Command 00/02 (no warn in emulated drive yet)
    # with pytest.warns(UserWarning, match="ERROR status: 00/02"):
    nvme0n1.send_cmd(0x7d, qpair, buf, 1, slba&0xffffffff+10, slba>>32).waitdone()


def test_zone_append(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones):
    zone_index = int(random.randrange(num_of_zones))
    slba = zone_size * zone_index
    zone = Zone(qpair, nvme0n1, slba)
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))
    zone.reset()

    zone.append(qpair, buf, 1, slba).waitdone()
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))

    zone.append(qpair, buf, 1, slba).waitdone()
    logging.info("Append Zone 0x%x, zslba: 0x%x, wp:0x%x" % (zone_index, slba, zone.wpointer))
    # zone append not from the zslba,Invalid Field in Command 00/02 (no warn in emulated drive yet)
    # with pytest.warns(UserWarning, match="ERROR status: 00/02"):
    zone.append(qpair, buf, 1, slba+10).waitdone()

    # I/O Command Set Profile (Feature Identifier 19h)
def test_iocmd_set_profile(nvme0, nvme0n1, qpair, buf):
    cdw0 = nvme0.getfeatures(0x19).waitdone()
    iocsci = cdw0 & 0xff
    logging.info("I/O Command Set Combination Index:0x%x" % iocsci)
    cdw0 = nvme0.getfeatures(7).waitdone()
    logging.info("Number of Queue:0x%x" % cdw0)

def test_zone_info(nvme0, buf):
    nvme0.identify(buf, nsid=1, cns=5, csi=2).waitdone()
    mar = buf.data(7, 4)
    logging.info("Maximum Active Resources (MAR): 0x%x" % mar)
    mor = buf.data(11, 8)
    logging.info("Maximum Open Resources (MAR): 0x%x" % mor)


def test_max_open_zone(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones, zslba_list):
    nvme0.identify(buf, nsid=1, cns=5, csi=2).waitdone()
    mor = buf.data(11, 8)
    logging.info("Maximum Open Resources (MAR): 0x%x" % mor)

    if (mor == 0xffffffff):
        pytest.skip("No Max open zone limit")
    else:
        assert mor < num_of_zones

        for zone_index, slba in enumerate(zslba_list):
            z0 = Zone(qpair, nvme0n1, slba)
            z0.reset()
            if zone_index <= mor:
                z0.open()
                logging.info("open zone: %d" % zone_index)
            else:
                logging.info("Try to open extra zone: %d" % zone_index)
                with pytest.warns(UserWarning, match="ERROR status: 01/be"):
                    z0.open()

                break
        test_zns_management_receive(nvme0, nvme0n1, qpair, buf, zone_size, num_of_zones)
