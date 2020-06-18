import time
import pytest
import logging
import warnings

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_sanitize_operations_basic(nvme0, nvme0n1, buf):
    if nvme0.id_data(331, 328) == 0:  #L9
        pytest.skip("sanitize operation is not supported")  #L10

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  #L13

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()  #L17
        while buf.data(3, 2) & 0x7 != 1:  #L18
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1


def test_sanitize_operations_powercycle(nvme0, nvme0n1, buf, subsystem):
    if nvme0.id_data(331, 328) == 0:  #L9
        pytest.skip("sanitize operation is not supported")  #L10

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    
    # slow down the sanitize
    nvme0.setfeatures(0x2, cdw11=2).waitdone()
    nvme0.sanitize().waitdone()  #L13
    
    subsystem.power_cycle()
    nvme0.reset()

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()  #L17
        while buf.data(3, 2) & 0x7 != 1:  #L18
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()
            
    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1

    logging.info("verify data after sanitize")
    q = Qpair(nvme0, 8)
    nvme0n1.read(q, buf, 11, 1).waitdone()
    assert buf[0] == 0
    assert buf[511] == 0

    # read after sanitize
    nvme0n1.ioworker(io_size=8, lba_align=8,
                     region_start=0, region_end=256*1024*8, # 1GB space
                     lba_random=False, qdepth=16,
                     read_percentage=100, time=10).start().close()

    # recover power mode
    nvme0.setfeatures(0x2, cdw11=0).waitdone()
    q.delete()

    
def test_write_in_sanitize_operations(nvme0, nvme0n1, buf, qpair):
    if nvme0.id_data(331, 328) == 0:  #L9
        pytest.skip("sanitize operation is not supported")  #L10

    logging.info("supported sanitize operation: %d" % nvme0.id_data(331, 328))
    nvme0.sanitize().waitdone()  #L13

    with pytest.warns(UserWarning, match="ERROR status: 00/1d"):
        nvme0n1.write(qpair, buf, 0).waitdone()

    # check sanitize status in log page
    with pytest.warns(UserWarning, match="AER notification is triggered"):
        nvme0.getlogpage(0x81, buf, 20).waitdone()  #L17
        while buf.data(3, 2) & 0x7 != 1:  #L18
            time.sleep(1)
            nvme0.getlogpage(0x81, buf, 20).waitdone()  #L20
            progress = buf.data(1, 0)*100//0xffff
            logging.info("%d%%" % progress)
        # one more waitdone for AER
        nvme0.waitdone()

    # check sanitize status
    nvme0.getlogpage(0x81, buf, 20).waitdone()
    assert buf.data(3, 2) & 0x7 == 1


