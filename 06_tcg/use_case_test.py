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

import nvme as d
import scripts.tcg as tcg


def test_uct01_level0_discovery(nvme0):
    comid = tcg.Response(nvme0).receive().level0_discovery()
    assert comid >= 1


def test_uct02_properties(nvme0):
    host_properties = {
        b"MaxComPacketSize": 4096,
        b"MaxPacketSize": 4076,
        b"MaxIndTokenSize": 4040, 
    }
    
    comid = tcg.Response(nvme0).receive().level0_discovery()
    tcg.Command(nvme0, comid).properties(host_properties).send()
    tcg.Response(nvme0, comid).receive()


@pytest.mark.parametrize("new_passwd",
                         [b'123456',
                          b'1',
                          b'1234',
                          b'abcd',
                          b'123456789abcdef',
                          b'123456789abcdef0',
                          b'123456789abcdef0123456789abcdef0'])
def test_uct03_take_ownership(nvme0, new_passwd):
    # discovery
    comid = tcg.Response(nvme0).receive().level0_discovery()

    # take ownership
    tcg.Command(nvme0, comid).start_anybody_adminsp_session(0x65).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).get_msid_cpin_pin(hsn, tsn).send()
    password = tcg.Response(nvme0, comid).receive().get_c_pin_msid()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    tcg.Command(nvme0, comid).start_adminsp_session(0x66, password).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).set_sid_cpin_pin(hsn, tsn, new_passwd).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    # revert
    tcg.Command(nvme0, comid).start_adminsp_session(0x69, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).revert_tper(hsn, tsn).send()
    tcg.Response(nvme0, comid).receive()
    
