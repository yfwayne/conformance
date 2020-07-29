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


@pytest.fixture()
def cq(nvme0):
    ret = IOCQ(nvme0, 1, 10, PRP())
    yield ret
    ret.delete()

@pytest.fixture()
def sq(nvme0, cq):
    ret = IOSQ(nvme0, 1, 10, PRP(), cq.id)
    yield ret
    ret.delete()

    
def test_flush_with_read_write(nvme0, nvme0n1, qpair):
    # prepare data buffer and IO queue
    read_buf = Buffer(512)
    write_buf = Buffer(512)
    write_buf[10:21] = b'hello world'

    # send write and read command
    nvme0n1.write(qpair, write_buf, 0, 1).waitdone()
    nvme0n1.flush(qpair).waitdone()
    nvme0n1.read(qpair, read_buf, 0, 1).waitdone()
    assert read_buf[10:21] == b'hello world'


def test_read_invalid_nsid(nvme0, nvme0n1, cq, sq):
    # first cmd, invalid namespace
    cmd = SQE(0, 0xff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0x000b

    
def test_read_all_namespace(nvme0, nvme0n1, cq, sq):
    cq = IOCQ(nvme0, 1, 10, PRP())
    sq = IOSQ(nvme0, 1, 10, PRP(), cqid=1)

    # first cmd, invalid namespace
    cmd = SQE(0, 0xffffffff)
    sq[0] = cmd
    sq.tail = 1
    time.sleep(0.1)
    status = (cq[0][3]>>17)&0x7ff
    assert status == 0

