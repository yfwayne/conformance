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

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem, __version__


def test_dut_firmware_and_model_name(nvme0):
    logging.info(nvme0.id_data(63, 24, str))
    logging.info(nvme0.id_data(71, 64, str))
    logging.info("testing conformance with pynvme " + __version__)

    
def test_abort_all_aer_commands(nvme0):
    aerl = nvme0.id_data(259)+1
    logging.info(aerl)

    def aer_cb(cdw0, status):
        assert ((status&0xfff)>>1) == 0x0007
    # another one is sent in defaul nvme init
    for i in range(aerl-1):
        nvme0.aer(cb=aer_cb)

    # ASYNC LIMIT EXCEEDED (01/05)
    with pytest.warns(UserWarning, match="ERROR status: 01/05"):
        nvme0.aer()
        nvme0.getfeatures(7).waitdone()

    # no timeout happen on aer
    time.sleep(15)

    # ABORTED - BY REQUEST (00/07)
    logging.info("reap %d command, including abort, and also aer commands" % (100+aerl))
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        for i in range(100):
            nvme0.abort(127-i).waitdone()
        

def test_abort_specific_aer_command(nvme0):
    aborted = False
    def aer_cb(cpl):
        nonlocal aborted
        status = cpl[3]>>16
        if ((status&0xfff)>>1) == 0x0007:
            aborted = True
    nvme0.aer(cb=aer_cb)
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        nvme0.abort(nvme0.latest_cid).waitdone()
    assert aborted


def test_abort_abort_command(nvme0):
    nvme0.abort(0)
    nvme0.abort(nvme0.latest_cid)
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        nvme0.waitdone(2)

    nvme0.abort(0xffff)
    nvme0.abort(nvme0.latest_cid)
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        nvme0.waitdone(2)
    
    nvme0.aer()
    nvme0.abort(nvme0.latest_cid) # abort aer command
    nvme0.abort(nvme0.latest_cid) # abort abort command
    with pytest.warns(UserWarning, match="ERROR status: 00/07"):
        nvme0.waitdone(2)
    
