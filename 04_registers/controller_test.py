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


def test_controller_cap(nvme0):
    logging.info("cap: 0x%lx" % nvme0.cap)

    #verify mpsmax and mpsmin
    mps_min = (nvme0.cap>>48) & 0xf
    mps_max = (nvme0.cap>>52) & 0xf
    mps_max_size=2**(12+mps_max)
    mps_min_size=2**(12+mps_min)
    logging.info("mps_min_size :{}".format(mps_min_size))
    logging.info("mps_max_size :{}".format(mps_max_size))
    assert mps_max >= mps_min

    #verify cc.mps is smaller than mpsmin and laeger than mpsmax
    cc=nvme0[0x14]
    cc_mps= nvme0[0x14]>>6&0xf
    cc_mps_size=2**(12+cc_mps)
    logging.info("cc_mps_size:{}".format(cc_mps_size))
    assert cc_mps_size <=mps_max_size
    assert cc_mps_size >=mps_min_size

    css = (nvme0.cap>>37) & 0xff
    assert css == 1

    nssrs=nvme0.cap>>36&0x1
    assert nssrs==1


def test_controller_version(nvme0):
    logging.info("ver: 0x%x" % nvme0[8])
    assert (nvme0[8]>>16) == 1


def test_controller_cc(nvme0):
    logging.info("cc: 0x%x" % nvme0[0x14])
    assert (nvme0[0x14]>>16) == 0x46


def test_controller_reserved(nvme0):
    assert nvme0[0x18] == 0
    nvme0[0x18]=0x1111
    assert nvme0[0x18]==0


def test_controller_csts(nvme0):
    logging.info("csts: 0x%x" % nvme0[0x1c])
    assert nvme0[0x1c]&1 == 1


def test_controller_cap_to(nvme0):
    logging.info("cc :{}".format(nvme0[0x14]))
    logging.info("cap timeout :{}".format(nvme0.cap>>24&0xff))
    timeout=nvme0.cap>>24&0xff

    #change cc.en from '1' to '0'
    nvme0[0x14] = 0

    time_start=int(time.time())
    max_time=timeout *500 //1000

    #wait csts.rdy change from '1' to '0'
    while not (nvme0[0x1c]&0x1)==0:
        assert int(time.time())-time_start <= max_time


    if 0 != nvme0.init_adminq():
        raise NvmeEnumerateError("fail to init admin queue")

    #change cc.en from '0' to '1'
    nvme0[0x14] = 0x00460001

    #wait csts.rdy change from '0' to '1'
    time_start=int(time.time())
    while not (nvme0[0x1c]&0x1)==1:
        assert int(time.time())-time_start <= max_time



def test_controller_cap_mqes(nvme0):
    mqes=nvme0.cap&0xffff
    logging.info("mqes:{}".format(mqes))
    assert mqes >=1

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        cq = IOCQ(nvme0, 1, mqes+5, PRP())

    cq = IOCQ(nvme0, 1, mqes, PRP())
    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        sq = IOSQ(nvme0, 1, mqes+5, PRP(), cqid=1)


def test_controller_ams(nvme0):
    ams=nvme0.cap>>17&0x3
    logging.info("AMS:{}".format(ams))


def test_controller_intms_and_intmc(nvme0):
    intms=nvme0[0xc]
    intmc=nvme0[0x10]
    logging.info("intms:{},intmc:{}".format(intms,intmc))
    nvme0[0xc]=0x0
    nvme0[0x10]=0x0
    #verify intms and intmc do not change value
    assert nvme0[0xc]==intms
    assert nvme0[0x10]==intmc


def test_controller_cc_iocqes(nvme0):
    iocqes=nvme0[0x14]>>20&0xf
    logging.info("iocqes:{}".format(iocqes))

    cqes=nvme0.id_data(513,513)
    logging.info("CQES:{}".format(cqes))

    cqes_max=cqes>>4&0xf
    cqes_min=cqes &0xf
    logging.info("cqes_max:{},cqes_min:{}".format(cqes_max,cqes_min))
    assert cqes_max >= cqes_min
    assert cqes_min == 4

    assert iocqes >= cqes_min
    assert iocqes <= cqes_max

def test_controller_cc_iosqes(nvme0):
    iosqes=nvme0[0x14]>>16&0xf
    logging.info("iosqes:{}".format(iosqes))

    sqes=nvme0.id_data(512,512)
    logging.info("SQES:{}".format(sqes))

    sqes_max=sqes>>4&0xf
    sqes_min=sqes &0xf
    logging.info("sqes_max:{},sqes_min:{}".format(sqes_max,sqes_min))
    assert sqes_max >= sqes_min
    assert sqes_min == 6

    assert iosqes >= sqes_min
    assert iosqes <= sqes_max


def test_controller_cc_shn(nvme0,subsystem):
    cc=nvme0[0x14]
    logging.info("cc:{}".format(cc))
    shn=nvme0[0x14]>>14&0x3
    logging.info("shn:{}".format(shn))

    begin_time=time.time()
    subsystem.shutdown_notify()
    end_time=time.time()
    time_spend_normal=end_time-begin_time
    logging.info("normal shn ,time spend is {}".format(time_spend_normal))

    nvme0.reset()


def test_controller_cc_en(nvme0):
    en=nvme0[0x14]&0x1
    logging.info("en:{}".format(en))
    logging.info("cc:{}".format(nvme0[0x14]))
    assert nvme0[0x14] == 0x00460001

    cq = IOCQ(nvme0, 1, 3, PRP())
    sq = IOSQ(nvme0, 1, 3, PRP(), cqid=1)
    sq[0] = SQE(2, 1); sq.tail = 1; time.sleep(0.1)
    # check cq
    time.sleep(0.1)
    assert (cq[0][3]>>17)&0x3ff == 0x0000

    sq.delete()
    cq.delete()

    #change cc.en from '1' to '0'
    nvme0[0x14] = 0

    #wait csts.rdy change from '1' to '0'
    while not (nvme0[0x1c]&0x1)==0:
        pass

    nvme0.aer()
    try:
        nvme0.waitdone()
    except Exception as e:
        logging.warning(e)


    if 0 != nvme0.init_adminq():
        raise NvmeEnumerateError("fail to init admin queue")

    #change cc.en from '0' to '1'
    nvme0[0x14] = 0x00460001

    #wait csts.rdy change from '0' to '1'
    while not (nvme0[0x1c]&0x1)==1:
        pass

    assert nvme0[0x14] ==0x00460001


def test_controller_cc_css(nvme0):
    css=nvme0[0x14]>>4&0x7
    logging.info("css:{}".format(css))


def test_controller_mdts(nvme0,nvme0n1,qpair,buf):
    mps_min = (nvme0.cap>>48) & 0xf
    logging.info("mps_min:{}".format(mps_min))

    mdts=nvme0.id_data(77,77)
    logging.info("mdts:{}".format(mdts))
    max_data_size=(2**mdts)*(2**(12+mps_min))

    nvme0n1.ioworker(io_size=8,
                     lba_random=False,
                     qdepth=2,
                     region_end=100).start().close()

    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0n1.read(qpair, Buffer(4096*100), 0,max_data_size//512+5).waitdone()


    nvme0n1.read(qpair, Buffer(4096*100), 0,max_data_size//512-5).waitdone()

    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        nvme0n1.write(qpair, Buffer(4096*100), 0,max_data_size//512+5).waitdone()


    nvme0n1.write(qpair, Buffer(4096*100), 0,max_data_size//512-5).waitdone()
