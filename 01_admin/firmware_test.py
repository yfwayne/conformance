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


import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


@pytest.mark.parametrize("size", [4095, 10, 4095*2])
@pytest.mark.parametrize("offset", [0, 4096, 4096*2])
def test_fw_download_invalid_size(nvme0, size, offset):
    fwug = nvme0.id_data(319)
    if fwug == 0 or fwug == 0xff:
        pytest.skip("not applicable")
    fw_active = nvme0.id_data(256) & 0x4
    if fw_active == 0:
        pytest.skip(
            " controller does not support the fw Commit and fw Image Download cmds")

    buf = Buffer(size)
    with pytest.warns(UserWarning, match="ERROR status: (01/14|00/02)"):
        nvme0.fw_download(buf, offset, size).waitdone()


@pytest.mark.parametrize("size", [4096, 4096*2])
@pytest.mark.parametrize("offset", [10, 4095, 4095*2])
def test_fw_download_invalid_ofst(nvme0, size, offset):
    fwug = nvme0.id_data(319)
    if fwug == 0 or fwug == 0xff:
        pytest.skip("not applicable")
    fw_active = nvme0.id_data(256) & 0x4
    if fw_active == 0:
        pytest.skip(
            " controller does not support the fw Commit and fw Image Download cmds")

    buf = Buffer(size)
    with pytest.warns(UserWarning, match="ERROR status: (01/14|00/02)"):
        nvme0.fw_download(buf, offset, size).waitdone()


def test_firmware_commit(nvme0):
    frmw = nvme0.id_data(260)
    slot1_ro = frmw&1
    slot_count = (frmw>>1)&7
    logging.info(slot1_ro)
    logging.info(slot_count)
    
    buf = Buffer(4096*16)
    nvme0.fw_download(buf, 0).waitdone()

    logging.info("commit to invalid firmware slot")
    with pytest.warns(UserWarning, match="ERROR status: 01/07"):
        nvme0.fw_commit(0, 0).waitdone()

    if slot_count != 7:
        for slot in range(slot_count+1, 8):
            with pytest.warns(UserWarning, match="ERROR status: 01/06"):
                nvme0.fw_commit(slot, 2).waitdone()

    logging.info("commit with an invalid firmware image")
    for slot in range(2, slot_count+1):
        with pytest.warns(UserWarning, match="ERROR status: 01/07"):
            nvme0.fw_commit(slot, 0).waitdone()
        
    with pytest.warns(UserWarning, match="ERROR status: 01/07"):
        nvme0.fw_commit(1, 0).waitdone()
