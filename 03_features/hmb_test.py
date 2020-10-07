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


def test_hmb_single_buffer(nvme0, nvme0n1):
    hmb_size = nvme0.id_data(275, 272)
    if hmb_size == 0:
        pytest.skip("hmb is not supported")

    # allocate host memory
    logging.info(hmb_size)
    hmb_buf = Buffer(hmb_size*4096*2)
    hmb_buf_2 = Buffer(hmb_size*4096*2)  # reserve more buffer
    hmb_buf_3 = Buffer(hmb_size*4096*2)
    logging.info(hex(hmb_buf.phys_addr))
    logging.info(hex(hmb_buf_2.phys_addr))
    logging.info(hex(hmb_buf_3.phys_addr))
    del hmb_buf
    del hmb_buf_3

    # build the hmb list by 1MB chunks
    chunk_size = 0x100000
    chunk_per_page = chunk_size//4096
    hmb_list_buf = Buffer(4096)
    chunk_count = hmb_size*4096//chunk_size
    logging.info(chunk_count)
    addr = ((hmb_buf_2.phys_addr+0x200000)>>21)<<21  # align to 2MB
    for i in range(chunk_count):
        logging.info(hex(addr))
        hmb_list_buf[i*16:i*16+8] = addr.to_bytes(8, 'little')
        hmb_list_buf[i*16+8:i*16+12] = chunk_per_page.to_bytes(4, 'little')
        addr += chunk_size

    # enable hmb
    hmb_list_phys = hmb_list_buf.phys_addr
    nvme0.setfeatures(0x0d,
                      cdw11=1,
                      cdw12=hmb_size,
                      cdw13=hmb_list_phys&0xffffffff,
                      cdw14=hmb_list_phys>>32,
                      cdw15=chunk_count).waitdone()

    # test with IO
    for i in range(10):
        logging.info(i)
        with nvme0n1.ioworker(io_size=8,
                              lba_random=False,
                              qdepth=8,
                              read_percentage=0,
                              time=3):
            pass

    # disable hmb
    nvme0.setfeatures(0x0d, cdw11=0).waitdone()
    assert hmb_list_buf
    assert hmb_buf_2
    logging.info(hmb_list_buf.dump(64))
    logging.info(hmb_buf_2.dump(64))

    
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

    return
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
    
    
