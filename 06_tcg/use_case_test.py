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
import scripts.tcg as tcg


@pytest.fixture()
def comid(nvme0):
    return tcg.Response(nvme0).receive().level0_discovery()


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
def test_uct03_take_ownership(nvme0, comid, new_passwd):
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
    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
    tcg.Command(nvme0, comid).start_adminsp_session(0x69, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).revert_tper(hsn, tsn).send()
    tcg.Response(nvme0, comid).receive()
    nvme0.timeout = orig_timeout


def test_uct04_activate_locking_sp(nvme0, comid, new_passwd=b'123456'):
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

    # activate locking sp
    tcg.Command(nvme0, comid).start_adminsp_session(0x66, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).get_locking_sp_lifecycle(hsn, tsn).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).activate(hsn, tsn).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()


def test_uct05_configuring_authorities(nvme0, comid, new_passwd=b'123456'):
    # enable user1 and passwd
    tcg.Command(nvme0, comid).start_auth_session(0x66, 0, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).enable_user(hsn, tsn, 1).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).set_new_passwd(hsn, tsn, 1, b"111111").send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    # admin auth session
    tcg.Command(nvme0, comid).start_auth_session(0x66, 0, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    # user auth session and change passwd
    tcg.Command(nvme0, comid).start_auth_session(0x66, 1, b"111111").send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).set_new_passwd(hsn, tsn, 1, b"111111").send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()


def test_uct06_configuring_locking_objects(nvme0, nvme0n1, qpair, subsystem, verify, comid, new_passwd=b'123456'):
    # setup range and link to user1
    tcg.Command(nvme0, comid).start_auth_session(0x69, 0, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).setup_range(hsn, tsn, 1, 0, 64).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).lock_unlock_range(hsn, tsn, 1, False, False).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    # write and verify
    buf = d.Buffer(64*512, pvalue=0x5aa55aa5, ptype=32)
    nvme0n1.write(qpair, buf, 0, 64).waitdone()
    buf = d.Buffer(64*512)
    nvme0n1.read(qpair, buf, 0, 64).waitdone()
    assert buf.data(11, 8) == 0x5aa55aa5

    
@pytest.mark.skip(reason="subsystem")
def test_uct06_configuring_locking_objects_powercycle(nvme0, nvme0n1, subsystem, verify, comid, new_passwd=b'123456'):    
    subsystem.poweroff()
    time.sleep(5)
    subsystem.poweron()
    nvme0.reset()
    
    qpair = d.Qpair(nvme0, 10)
    with pytest.warns(UserWarning, match="ERROR status: 02/86"):
        nvme0n1.read(qpair, buf, 0, 64).waitdone()
    qpair.delete()
    

def test_uct07_unlocking_range(nvme0, nvme0n1, qpair, verify, comid, new_passwd=b'123456'):
    tcg.Command(nvme0, comid).start_auth_session(0x69, 0, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).lock_unlock_range(hsn, tsn, 1, False, False).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    buf = d.Buffer(64*512)
    nvme0n1.read(qpair, buf, 0, 64).waitdone()
    assert buf.data(11, 8) == 0x5aa55aa5


def test_uct08_erasing_range(nvme0, nvme0n1, qpair, verify, comid, new_passwd=b'123456'):
    # TODO: skip on pyrite

    # verify data before erasing
    buf = d.Buffer(64*512)
    nvme0n1.read(qpair, buf, 0, 64).waitdone()
    assert buf.data(11, 8) == 0x5aa55aa5

    # erasing
    tcg.Command(nvme0, comid).start_auth_session(0x69, 0, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).get_active_key(hsn, tsn, 1).send()
    prev_data = tcg.Response(nvme0, comid).receive().get_active_key()
    tcg.Command(nvme0, comid).gen_new_key(hsn, tsn, 1, prev_data).send()
    tcg.Response(nvme0, comid).receive()
    tcg.Command(nvme0, comid).end_session(hsn, tsn).send(False)
    tcg.Response(nvme0, comid).receive()

    # verify
    buf = d.Buffer(64*512)
    nvme0n1.read(qpair, buf, 0, 64).waitdone()
    assert buf.data(11, 8) == 0


def test_uct12_revert_locking_sp(nvme0, comid, new_passwd=b'123456'):
    # revert
    orig_timeout = nvme0.timeout
    nvme0.timeout = 100000
    tcg.Command(nvme0, comid).start_adminsp_session(0x69, new_passwd).send()
    hsn, tsn = tcg.Response(nvme0, comid).receive().start_session()
    tcg.Command(nvme0, comid).revert_tper(hsn, tsn).send()
    tcg.Response(nvme0, comid).receive()
    nvme0.timeout = orig_timeout
