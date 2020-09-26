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


def test_identify_all_nsid(nvme0):
    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0, cns=1).waitdone()
    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=0xff, cns=0).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=2, cns=0).waitdone()


def test_identify_namespace_id_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0x10).waitdone()
    nvme0.identify(buf, nsid=0, cns=0x10).waitdone()


def test_identify_active_controller_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=1, cns=0x12).waitdone()


def test_identify_controller_list(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=1, cns=0x13).waitdone()


def test_identify_global_namespace(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0).waitdone()


def test_identify_namespace(nvme0):
    if not nvme0.id_data(257, 256) & 0x8:
        pytest.skip("namespace management is not supported")

    buf = Buffer(4096)
    nvme0.identify(buf, nsid=0xffffffff, cns=0).waitdone()


def test_identify_namespace_id_list(nvme0, buf):
    nvme0.identify(buf, nsid=0, cns=2).waitdone()
    assert buf[0] == 1
    assert buf[16] == 0

    nvme0.identify(buf, nsid=1, cns=0).waitdone()
    print(buf.dump(64))
    assert buf[0] != 0
    for i in range(8):
        assert buf[i] == buf[i+8]


def test_identify_namespace_utilization(nvme0, nvme0n1, buf):
    q = Qpair(nvme0, 10)
    orig_nuse = nvme0n1.id_data(23, 16)
    logging.info(orig_nuse)

    # trim lba 0
    buf.set_dsm_range(0, 0, 8)
    nvme0n1.dsm(q, buf, 1).waitdone()
    nuse = nvme0n1.id_data(23, 16)
    logging.info(nuse)
    assert nuse <= orig_nuse

    # write lba 0
    nvme0n1.write(q, buf, 0, 8).waitdone()
    time.sleep(0.1)  # some drive may update it at background
    nuse = nvme0n1.id_data(23, 16)
    logging.info(nuse)
    assert nuse == orig_nuse


def test_identify_namespace_identification_descriptor(nvme0, buf):
    nvme0.identify(buf, nsid=1, cns=3).waitdone()
    logging.info(buf.dump(64))
    assert buf[0] != 0
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.identify(buf, nsid=0, cns=3).waitdone()


def test_identify_reserved_cns(nvme0, buf):
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.identify(buf, nsid=0, cns=0xff).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0.identify(buf, nsid=1, cns=0xff).waitdone()

def test_identify_nsze_ncap_nuse(nvme0, nvme0n1, buf):
    nsze = nvme0n1.id_data(7, 0)
    ncap = nvme0n1.id_data(15, 8)
    nuse = nvme0n1.id_data(23, 16)
    logging.info("nsze=0x%x,ncap=0x%x,nuse=0x%x" % (nsze,ncap,nuse))

    # Namespace Size >= Namespace Capacity >= Namespace Utilization
    assert nsze >= ncap >= nuse

    #if ANA reporting supported and in inaccessible or Persistent Loss state, nuse=0
    ana = nvme0.id_data(76, 76)
    ana_reporting = ana & 0x8
    ANACAP = nvme0.id_data(343, 343)
    inaccessible_loss = ANACAP & 0xc
    if ana_reporting and inaccessible_loss:
        assert nuse == 0
