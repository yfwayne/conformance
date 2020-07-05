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


def test_controller_cap(nvme0):
    logging.info("cap: 0x%lx" % nvme0.cap)
    
    mps_min = (nvme0.cap>>48) & 0xf
    mps_max = (nvme0.cap>>52) & 0xf
    assert mps_max >= mps_min

    css = (nvme0.cap>>37) & 0xff
    assert css == 1

    
def test_controller_version(nvme0):
    logging.info("cap: 0x%x" % nvme0[8])
    assert (nvme0[8]>>16) == 1


def test_controller_cc(nvme0):
    logging.info("cc: 0x%x" % nvme0[0x14])
    assert (nvme0[0x14]>>16) == 0x46

    
def test_controller_reserved(nvme0):
    assert nvme0[0x18] == 0

    
def test_controller_csts(nvme0):
    logging.info("csts: 0x%x" % nvme0[0x1c])
    assert nvme0[0x1c]&1 == 1
