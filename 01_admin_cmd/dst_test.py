import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


@pytest.mark.parametrize("nsid", [0, 1, 0xffffffff])
@pytest.mark.parametrize("stc", [1, 2])
def test_dst(nvme0, nsid, stc):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(stc, nsid).waitdone()

    # check dst log page till no dst in progress
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    while buf[0]:
        time.sleep(1)
        nvme0.getlogpage(0x6, buf, 32).waitdone()
        logging.info("current dst progress percentage: %d%%" % buf[1])


@pytest.mark.parametrize("nsid", [2, 3, 8, 10, 0xff, 0xfffffffe])
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_invalid_namespace(nvme0, nsid, stc):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    with pytest.warns(UserWarning, match="ERROR status: 00/0b"):
        nvme0.dst(stc, nsid).waitdone()


@pytest.mark.parametrize("nsid", [0, 1, 0xffffffff])
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_in_progress(nvme0, nsid, stc):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(stc, nsid).waitdone()

    with pytest.warns(UserWarning, match="ERROR status: 01/1d"):
        nvme0.dst(stc, nsid).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/1d"):
        nvme0.dst(stc, nsid).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/1d"):
        nvme0.dst(stc, nsid).waitdone()

    # check dst log page till dst finishes
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    while buf[0]:
        time.sleep(1)
        nvme0.getlogpage(0x6, buf, 32).waitdone()
        logging.info("current dst progress percentage: %d%%" % buf[1])

        
@pytest.mark.parametrize("nsid", [0, 1, 0xffffffff])
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_abort(nvme0, nsid, stc):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(stc, nsid).waitdone()
    
    nvme0.dst(0xf, nsid).waitdone()

    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
        

def test_dst_invalid_stc(nvme0, nsid=1):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    with pytest.warns(UserWarning, match="ERROR status: 01/0a"):
        nvme0.dst(0, nsid).waitdone()
    with pytest.warns(UserWarning, match="ERROR status: 01/0a"):
        nvme0.dst(0xe, nsid).waitdone()
    nvme0.dst(0xf, nsid).waitdone()

    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_abort_by_format(nvme0, nvme0n1, stc, nsid=1):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(stc, nsid).waitdone()

    nvme0.format(0, 0).waitdone()

    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    

def test_dst_short_abort_by_reset(nvme0):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(1, 0).waitdone()

    nvme0.reset()
    
    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]


def test_dst_extended_abort_by_reset(nvme0):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(2, 0).waitdone()

    nvme0.reset()
    
    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert buf[0]

    nvme0.dst(0xf, 0).waitdone()
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    
def test_pcie_reset_setup(pcie, nvme0):
    pcie.reset()
    nvme0.reset()
    
    
def test_dst_extended_abort_by_subsystem_reset(nvme0, subsystem):
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
    
    nvme0.dst(2, 0).waitdone()

    time.sleep(2)
    subsystem.reset()
    nvme0.reset()
    
    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert buf[0]

    nvme0.dst(0xf, 0).waitdone()
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_abort_by_sanitize(nvme0, nvme0n1, stc, nsid=1):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    # aer callback function
    def cb(cdw0, status):
        warnings.warn("AER notification is triggered")
    nvme0.aer(cb)
    
    nvme0.dst(stc, nsid).waitdone()

    nvme0.sanitize().waitdone()  # sanitize command is completed

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            nvme0.getlogpage(0x81, buf, 20).waitdone()
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
            time.sleep(1)    
        nvme0.waitdone()  # aer complete

    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    
@pytest.mark.parametrize("stc", [1, 2])
def test_dst_after_sanitize(nvme0, nvme0n1, stc, nsid=1):
    if nvme0.id_data(331, 328) == 0:
        pytest.skip("sanitize operation is not supported")

    # check dst
    buf = Buffer(4096)
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  # sanitize command is completed

    nvme0.dst(stc, nsid).waitdone()

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()
        while buf.data(3, 2) & 0x7 != 1:  # sanitize operation is not completed
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()
        
    # check if dst aborted
    nvme0.getlogpage(0x6, buf, 32).waitdone()
    assert not buf[0]
