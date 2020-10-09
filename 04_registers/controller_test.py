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


def test_controller_version(nvme0):
    logging.info("ver: 0x%x" % nvme0[8])
    assert (nvme0[8]>>16) == 1


def test_controller_cc(nvme0):
    logging.info("cc: 0x%x" % nvme0[0x14])
    assert (nvme0[0x14]>>16) == 0x46


def test_controller_reserved(nvme0):
    assert nvme0[0x18] == 0
    nvme0[0x18]=1234
    assert nvme0[0x18] == 0


def test_controller_csts(nvme0):
    logging.info("csts: 0x%x" % nvme0[0x1c])
    assert nvme0[0x1c]&1 == 1


def test_controller_cap_to(nvme0):
    logging.info("cc: {}".format(nvme0[0x14]))
    logging.info("cap timeout: {}".format(nvme0.cap>>24&0xff))
    timeout = nvme0.cap>>24&0xff
    max_time = timeout*500//1000

    #change cc.en from '1' to '0'
    nvme0[0x14] = 0

    time_start = time.time()
    #wait csts.rdy change from '1' to '0'
    while (nvme0[0x1c]&0x1)==0: pass
    assert time.time()-time_start < max_time

    #change cc.en from '0' to '1'
    nvme0[0x14] = 0x00460001

    #wait csts.rdy change from '0' to '1'
    time_start=int(time.time())
    while (nvme0[0x1c]&0x1)==1: pass
    assert time.time()-time_start < max_time


def test_controller_cap_mqes(nvme0):
    mqes = 1+(nvme0.cap&0xffff)
    logging.info(mqes)
    assert mqes >= 2
    
    if mqes == 64*1024:
        pytest.skip("mqes is maximum")

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        cq = IOCQ(nvme0, 1, mqes+1, PRP())

    cq = IOCQ(nvme0, 1, mqes, PRP())
    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        sq = IOSQ(nvme0, 1, mqes+1, PRP(), cqid=1)


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


def test_controller_mdts(nvme0,nvme0n1):
    if nvme0.mdts == 1024*1024: # up to 1MB
        pytest.skip("mdts is maximum")

    mps_min = (nvme0.cap>>48) & 0xf
    logging.info("mps_min:{}".format(mps_min))

    mdts=nvme0.id_data(77,77)
    logging.info("mdts:{}".format(mdts))
    max_data_size=(2**mdts)*(2**(12+mps_min))
    logging.info(max_data_size)
    max_pages=max_data_size//4//1024
    pages=max_pages-1
    max_lba=max_data_size//512

    cq = IOCQ(nvme0, 1, 5, PRP())
    sq = IOSQ(nvme0, 1, 5, PRP(), cqid=1)

    # prp for the long buffer
    write_buf_1 = PRP(ptype=32, pvalue=0xaaaaaaaa)
    prp_list = PRPList()
    prp_list_head = prp_list
    while pages:
        for i in range(511):
            if pages:
                prp_list[i] = PRP()
                pages -= 1
                logging.debug(pages)

        if pages>1:
            tmp = PRPList()
            prp_list[511] = tmp
            prp_list = tmp
            logging.debug("prp_list")

        elif pages==1:
            prp_list[511] = PRP()
            pages -= 1
            logging.debug(pages)

    w1 = SQE(1, 1)
    w1.prp1 = write_buf_1
    w1.prp2 = prp_list_head
    w1[12] = max_lba-1 # 0based, nlba
    w1.cid = 0x123
    sq[0] = w1
    sq.tail = 1

    time.sleep(1)
    cqe = CQE(cq[0])
    logging.info(cqe)
    assert cqe.p == 1
    assert cqe.cid == 0x123
    assert cqe.sqhd == 1
    assert cqe.status == 0
    cq.head = 1

    w2 = SQE(1, 1)
    w2.prp1 = write_buf_1
    w2.prp2 = prp_list_head
    w2[12] = max_lba # 0based, nlba
    w2.cid = 0x234
    sq[1] = w2
    sq.tail = 2

    time.sleep(1)
    cqe = CQE(cq[1])
    logging.info(cqe)
    assert cqe.p == 1
    assert cqe.cid == 0x234
    assert cqe.sqhd == 2
    assert cqe.status == 2
    cq.head = 2

    r1 = SQE(2, 1)
    r1.prp1 = write_buf_1
    r1.prp2 = prp_list_head
    r1[12] = max_lba # 0based, nlba
    r1.cid = 0x345
    sq[2] = r1
    sq.tail = 3

    time.sleep(1)
    cqe = CQE(cq[2])
    logging.info(cqe)
    assert cqe.p == 1
    assert cqe.cid == 0x345
    assert cqe.sqhd == 3
    assert cqe.status == 2
    cq.head = 3

    r2 = SQE(2, 1)
    r2.prp1 = write_buf_1
    r2.prp2 = prp_list_head
    r2[12] = max_lba-1 # 0based, nlba
    r2.cid = 0x456
    sq[3] = r2
    sq.tail = 4

    time.sleep(1)
    cqe = CQE(cq[3])
    logging.info(cqe)
    assert cqe.p == 1
    assert cqe.cid == 0x456
    assert cqe.sqhd == 4
    assert cqe.status == 0
    cq.head = 4

    sq.delete()
    cq.delete()
