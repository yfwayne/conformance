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
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


@pytest.fixture(scope="function")
def ncqa(nvme0):
    num_of_queue = 0
    def test_greater_id(cdw0, status):
        nonlocal num_of_queue
        num_of_queue = 1+(cdw0&0xffff)
    nvme0.getfeatures(7, cb=test_greater_id).waitdone()
    logging.info("number of queue: %d" % num_of_queue)
    return num_of_queue


@pytest.fixture(scope="function")
def mqes(nvme0):
    num_of_entry = (nvme0.cap&0xffff) + 1
    logging.info("number of entry: %d" % num_of_entry)
    return num_of_entry


def test_create_cq_basic_operation(nvme0, nvme0n1, buf, qpair):
    for i in range(10):
        nvme0n1.read(qpair, buf, 0)
    qpair.waitdone(10)


def test_create_cq_with_invalid_id(nvme0, ncqa):
    # pass case
    cq = IOCQ(nvme0, 5, 10, PRP(4096))

    # cqid: 0
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOCQ(nvme0, 0, 10, PRP(4096))

    # cqid: 0xffff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOCQ(nvme0, 0xffff, 10, PRP(4096))

    # cqid: larger than supported number of queue
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOCQ(nvme0, ncqa+1, 10, PRP(4096))

    # cqid: duplicated cqid
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOCQ(nvme0, 5, 10, PRP(4096))
    cq.delete()

    # cqid: 0xff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOCQ(nvme0, ncqa+0xff, 10, PRP(4096))


def test_create_sq_with_invalid_id(nvme0, ncqa):
    # helper cq: id 1
    cq = IOCQ(nvme0, 1, 10, PRP(4096))

    # pass case
    sq = IOSQ(nvme0, 5, 10, PRP(4096), cqid=1)

    # sqid: 0
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 0, 10, PRP(4096), cqid=1)

    # sqid: 0xffff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 0xffff, 10, PRP(4096), cqid=1)

    # sqid: larger than supported number of queue
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, ncqa+1, 10, PRP(4096), cqid=1)

    # sqid: duplicated cqid
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 5, 10, PRP(4096), cqid=1)

    # sqid: 0
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 0, 10, PRP(4096), cqid=1)

    # sqid: 0xdead
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 0xdead, 10, PRP(4096), cqid=1)

    # sqid: 0xff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, ncqa+0xff, 10, PRP(4096), cqid=1)

    sq.delete()
    cq.delete()


def test_delete_cq_with_invalid_id(nvme0, ncqa):
    def delete_cq(nvme0, qid):
        nvme0.send_cmd(0x04, cdw10 = qid).waitdone()

    # pass case
    IOCQ(nvme0, 5, 10, PRP(4096))
    delete_cq(nvme0, 5)

    # cqid: 0
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_cq(nvme0, 0)

    # cqid: 0xffff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_cq(nvme0, 0xffff)

    # cqid: larger than supported number of queue
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_cq(nvme0, ncqa+1)

    # cqid: duplicated cqid
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_cq(nvme0, ncqa+0xff)

    # cqid: not existed
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_cq(nvme0, 5)


def test_delete_sq_with_invalid_id(nvme0, ncqa):
    def delete_sq(nvme0, qid):
        nvme0.send_cmd(0x00, cdw10 = qid).waitdone()

    # pass case
    cq = IOCQ(nvme0, 1, 10, PRP(4096))
    IOSQ(nvme0, 5, 10, PRP(4096), cqid=1)
    delete_sq(nvme0, 5)
    cq.delete()

    # sqid: 0
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_sq(nvme0, 0)

    # sqid: 0xffff
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_sq(nvme0, 0xffff)

    # sqid: larger than supported number of queue
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_sq(nvme0, ncqa+1)

    # sqid: duplicated cqid
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_sq(nvme0, ncqa+0xff)

    # sqid: not existed
    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        delete_sq(nvme0, 5)


def test_delete_cq_with_sq(nvme0, nsq=3, sqid=2):
    cq = IOCQ(nvme0, 2, 10, PRP(4096))
    sq_list = []
    for i in range(nsq):
        sq_list.append(IOSQ(nvme0, sqid+i, 10, PRP(4096), cqid=2))

    # delete cq before corresponding sq
    with pytest.warns(UserWarning, match="ERROR status: 01/0c"):
        cq.delete()

    for sq in sq_list:
        sq.delete()
    cq.delete()


def test_create_cq_with_invalid_queue_size(nvme0, mqes):
    if mqes == 0x10000:
        pytest.skip("no invalid queue size")
        
    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, 0xffff, PRP(4096))

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, 1, PRP(4096))

    IOCQ(nvme0, 1, mqes-2, PRP(4096)).delete()
    IOCQ(nvme0, 1, mqes-1, PRP(4096)).delete()
    IOCQ(nvme0, 1, mqes, PRP(4096)).delete()

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, mqes+1, PRP(4096))

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, mqes+2, PRP(4096))

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, mqes+0xff, PRP(4096))

    # empty queue
    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOCQ(nvme0, 1, 1, PRP(4096))
    with pytest.raises(AssertionError):
        IOCQ(nvme0, 1, 0, PRP(4096))

    IOCQ(nvme0, 1, 2, PRP(4096))


def test_create_sq_with_invalid_queue_size(nvme0, mqes):
    if mqes == 0x10000:
        pytest.skip("no invalid queue size")
        
    cq = IOCQ(nvme0, 2, 10, PRP(4096))

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, 0xffff, PRP(4096), cqid=2)

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, 1, PRP(4096), cqid=2)

    IOSQ(nvme0, 1, mqes-2, PRP(4096), cqid=2).delete()
    IOSQ(nvme0, 1, mqes-1, PRP(4096), cqid=2).delete()
    IOSQ(nvme0, 1, mqes, PRP(4096), cqid=2).delete()

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, mqes+1, PRP(4096), cqid=2)

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, mqes+2, PRP(4096), cqid=2)

    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, mqes+0xff, PRP(4096), cqid=2)

    # empty queue
    with pytest.warns(UserWarning, match="ERROR status: 01/02"):
        IOSQ(nvme0, 1, 1, PRP(4096), cqid=2)
    with pytest.raises(AssertionError):
        IOSQ(nvme0, 1, 0, PRP(4096), cqid=2)

    IOSQ(nvme0, 1, 2, PRP(4096), cqid=2).delete()
    cq.delete()


def test_create_sq_physically_contiguous(nvme0):
    if not nvme0.cap&0x10000:
        pytest.skip("pc is not required")

    cq = IOCQ(nvme0, 2, 10, PRP(4096))
    with pytest.warns(UserWarning, match="ERROR status: 00/02"):
        IOSQ(nvme0, 1, 2, PRP(4096), pc=False, cqid=2)
    IOSQ(nvme0, 1, 2, PRP(4096), pc=True, cqid=2).delete()
    cq.delete()


def test_create_sq_with_invalid_cqid(nvme0,mqes):
    cdw0=nvme0.getfeatures(0x07).waitdone()
    ncqr=(cdw0>>16)&0xffff

    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 1, mqes, PRP(4096), cqid=0)

    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 1, mqes, PRP(4096), cqid=0xffff)

    with pytest.warns(UserWarning, match="ERROR status: 01/00"):
        IOSQ(nvme0, 1, mqes, PRP(4096), cqid=ncqr)

    with pytest.warns(UserWarning, match="ERROR status: 01/00"):
        IOSQ(nvme0, 1, mqes, PRP(4096), cqid=ncqr+1)

    with pytest.warns(UserWarning, match="ERROR status: 01/01"):
        IOSQ(nvme0, 1, mqes, PRP(4096), cqid=ncqr+0xff)


def test_create_cq_invalid_interrupt_vector(nvme0, pcie):
    msicap_addr = pcie.cap_offset(0x05)
    msicap = pcie.register(msicap_addr, 4)
    logging.info("MSI Enable: %d" % ((msicap>>16)&0x1))
    logging.info("Multiple Message Capable: %d" % ((msicap>>17)&0x7))
    logging.info("Multiple Message Enable: %d" % ((msicap>>20)&0x7))
    if ((msicap>>20)&0x7) :
        invalid_iv = ((msicap>>17)&0x7) + 2
        logging.info("invalid_iv: %d" % invalid_iv)

    msixcap_addr = pcie.cap_offset(0x11)
    msixcap = pcie.register(msixcap_addr, 4)
    logging.info("Table Size: %d" % ((msixcap>>16)&0x3ff))
    logging.info("MSI-X Enable: %d" % ((msixcap>>31)&0x1))
    if ((msixcap>>31)&0x1) :
        invalid_iv = ((msixcap>>16)&0x3ff) + 2
        logging.info("invalid_iv: %d" % invalid_iv)

    with pytest.warns(UserWarning, match="ERROR status: 01/08"):
        IOCQ(nvme0, 1, 10, PRP(4096), iv=invalid_iv, ien=True)
    with pytest.warns(UserWarning, match="ERROR status: 01/08"):
        IOCQ(nvme0, 1, 10, PRP(4096), iv=2047, ien=True)


def test_create_cq_invalid_queue_address_offset(nvme0):
    queue = PRP(4096)
    queue.offset = 1
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOCQ(nvme0, 1, 10, queue)


def test_create_sq_invalid_queue_address_offset(nvme0):
    cq = IOCQ(nvme0, 3, 10, PRP(4096))

    queue = PRP(4096)
    queue.offset = 1
    with pytest.warns(UserWarning, match="ERROR status: 00/13"):
        IOSQ(nvme0, 1, 10, queue, cqid=3)

    cq.delete()

