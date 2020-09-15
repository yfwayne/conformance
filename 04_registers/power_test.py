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
import nvme as d

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_pcie_pmcsr_d3hot(pcie, nvme0, buf):
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    with pytest.raises(TimeoutError):
        with pytest.warns(UserWarning, match="ERROR status: 07/ff"):
            nvme0.identify(buf).waitdone()

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    
def test_pcie_capability_d3hot(pcie, nvme0n1):
    # get pm register
    assert None != pcie.cap_offset(1)
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    assert pcie.power_state == 0

    # set d3hot
    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)

    # and exit d3hot
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    # again
    pcie.power_state = 0
    logging.info("curent power state: %d" % pcie.power_state)
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.power_state == 0
    

def test_pcie_aspm_L1(pcie, nvme0, buf):
    #ASPM L1
    pcie.aspm = 2
    buf = d.Buffer(4096, 'controller identify data')
    nvme0.identify(buf, 0, 1).waitdone()
    time.sleep(1)
    #ASPM L0
    pcie.aspm = 0
    logging.info("model number: %s" % nvme0.id_data(63, 24, str))

def test_pcie_aspm_l1_and_d3hot(pcie, nvme0n1):
    pcie.aspm = 2
    assert pcie.aspm == 2
    pcie.power_state = 3
    time.sleep(1)
    pcie.power_state = 0
    pcie.aspm = 0
    assert pcie.aspm == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    pcie.power_state = 3
    assert pcie.power_state == 3
    pcie.aspm = 2
    time.sleep(1)
    pcie.aspm = 0
    assert pcie.aspm == 0
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.aspm == 0

    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()


def test_pcie_ioworker_aspm(pcie, nvme0, buf):
    region_end = 256*1000*1000  # 1GB
    qdepth = min(1024, 1+(nvme0.cap&0xffff))
    
    # get the unsafe shutdown count
    def power_cycle_count():
        buf = d.Buffer(4096)
        nvme0.getlogpage(2, buf, 512).waitdone()
        return buf.data(115, 112)
    
    # run the test one by one
    subsystem = d.Subsystem(nvme0)
    nvme0n1 = d.Namespace(nvme0, 1, region_end)
    orig_unsafe_count = power_cycle_count()
    logging.info("power cycle count: %d" % orig_unsafe_count)

    # 128K random write, changing aspm
    cmdlog_list = [None]*1000
    with nvme0n1.ioworker(io_size=256,
                          lba_random=True,
                          read_percentage=30,
                          region_end=region_end,
                          time=20,
                          qdepth=qdepth, 
                          output_cmdlog_list=cmdlog_list):
        for i in range(10):
            time.sleep(1)
            pcie.aspm = 2
            time.sleep(1)
            pcie.aspm = 0
        
    # verify data in cmdlog_list
    time.sleep(5)
    assert True == nvme0n1.verify_enable(True)
    logging.info(cmdlog_list[-10:])
    read_buf = d.Buffer(256*512)
    qpair = d.Qpair(nvme0, 10)
    for cmd in cmdlog_list:
        slba = cmd[0]
        nlba = cmd[1]
        op = cmd[2]
        if nlba:
            def read_cb(cdw0, status1):
                nonlocal _slba
                if status1>>1:
                    logging.info("slba %d, 0x%x, _slba 0x%x, status 0x%x" % \
                                 (slba, slba, _slba, status1>>1))
                    
            logging.debug("verify slba %d, nlba %d" % (slba, nlba))
            _nlba = nlba//16
            for i in range(16):
                _slba = slba+i*_nlba
                nvme0n1.read(qpair, read_buf, _slba, _nlba, cb=read_cb).waitdone()
            
            # re-write to clear CRC mismatch
            nvme0n1.write(qpair, read_buf, slba, nlba, cb=read_cb).waitdone()
    qpair.delete()
    nvme0n1.close()

    # verify unsafe shutdown count
    unsafe_count = power_cycle_count()
    logging.info("power cycle count: %d" % unsafe_count)
    assert unsafe_count == orig_unsafe_count
    time.sleep(5)
    pcie.aspm = 0 

