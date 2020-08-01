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
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


@pytest.fixture(scope="function")
def hmb(nvme0):
    hmb_size = nvme0.id_data(275, 272)
    if hmb_size == 0:
        pytest.skip("hmb is not supported")
    
    hmb_buf = Buffer(4096*hmb_size)
    assert hmb_buf
    hmb_list_buf = Buffer(4096)
    assert hmb_list_buf
        
    hmb_list_buf[0:8] = hmb_buf.phys_addr.to_bytes(8, 'little')
    hmb_list_buf[8:12] = hmb_size.to_bytes(4, 'little')
    hmb_list_phys = hmb_list_buf.phys_addr

    # enable hmb
    nvme0.setfeatures(0x0d,
                      cdw11=1,
                      cdw12=hmb_size,
                      cdw13=hmb_list_phys&0xffffffff,
                      cdw14=hmb_list_phys>>32,
                      cdw15=1).waitdone()
    yield

    # disable hmb
    nvme0.setfeatures(0x0d, cdw11=0).waitdone()
    del hmb_buf
    del hmb_list_buf


def test_single_hmb(nvme0, nvme0n1, hmb):
    hmb_size = nvme0.id_data(275, 272)
    if hmb_size == 0:
        pytest.skip("hmb is not supported")
        
    logging.info(hmb_size)
    for i in range(3):
        logging.info(i)
        with nvme0n1.ioworker(io_size=8,
                              lba_random=False,
                              qdepth=8,
                              read_percentage=0,
                              time=3):
            pass

        
def _test_reset_with_hmb_disabled(nvme0, nvme0n1, buf):
    hmb_size = nvme0.id_data(275, 272)
    if hmb_size == 0:
        pytest.skip("hmb is not supported")
        
    nvme0n1.format(512)

    # single host memory buffer
    hmb_buf = Buffer(4096*hmb_size+4096)
    assert hmb_buf
    hmb_list_buf = Buffer(4096)
    assert hmb_list_buf
    hmb_list_buf[0:8] = hmb_buf.phys_addr.to_bytes(8, 'little')
    hmb_list_buf[8:12] = hmb_size.to_bytes(4, 'little')
    hmb_list_phys = hmb_list_buf.phys_addr
    
    for i in range(3):
        logging.info(i)
        with nvme0n1.ioworker(io_size=8,
                              lba_random=False,
                              qdepth=8,
                              read_percentage=0,
                              time=30):
            time.sleep(5)
            
            # enable hmb    
            nvme0.setfeatures(0x0d,
                              cdw11=1,
                              cdw12=hmb_size,
                              cdw13=hmb_list_phys&0xffffffff,
                              cdw14=hmb_list_phys>>32,
                              cdw15=1).waitdone()
            time.sleep(5)

            #disable hmb
            nvme0.setfeatures(0x0d, cdw11=0).waitdone()
            time.sleep(5)
            
            nvme0.reset()

    logging.info(hmb_buf.dump(4096*2))
    del hmb_buf
    del hmb_list_buf
    

def test_multiple_hmb_buffer(nvme0, nvme0n1, buf):
    hmb_size = nvme0.id_data(275, 272)
    if hmb_size == 0:
        pytest.skip("hmb is not supported")
        
    # single host memory buffer
    hmb_buffer_list = []
    hmb_list_buf = Buffer(hmb_size*16)
    assert hmb_list_buf
    for i in range(hmb_size):
        hmb_buf = Buffer()
        assert hmb_buf
        hmb_buffer_list.append(hmb_buf)
        hmb_list_buf[16*i+0 : 16*i+8] = hmb_buf.phys_addr.to_bytes(8, 'little')
        hmb_list_buf[16*i+8 : 16*i+12] = hmb_size.to_bytes(4, 'little')
    hmb_list_phys = hmb_list_buf.phys_addr

    # enable hmb    
    nvme0.setfeatures(0x0d,
                      cdw11=1,
                      cdw12=hmb_size,
                      cdw13=hmb_list_phys&0xffffffff,
                      cdw14=hmb_list_phys>>32,
                      cdw15=hmb_size).waitdone()
    
    for i in range(3):
        logging.info(i)
        with nvme0n1.ioworker(io_size=8,
                              lba_random=False,
                              qdepth=8,
                              read_percentage=0,
                              time=3):
            pass

    #disable hmb
    nvme0.setfeatures(0x0d, cdw11=0).waitdone()
    del hmb_buffer_list
    del hmb_list_buf
    
    
