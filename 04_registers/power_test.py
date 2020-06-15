import time
import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem


def test_pcie_pmcsr_d3hot(pcie, nvme0, buf):
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    # set d3hot
    pcie[pm_offset+4] = pmcs|3     #D3hot
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)

    with pytest.raises(TimeoutError):
        with pytest.warns(UserWarning, match="ERROR status: 07/ff"):
            nvme0.identify(buf).waitdone()

    # and exit d3hot
    time.sleep(1)
    pcie[pm_offset+4] = pmcs&0xfc  #D0
    pmcs = pcie[pm_offset+4]
    logging.info("pmcs %x" % pmcs)
    nvme0.identify(buf).waitdone()

    
def test_pcie_capability_d3hot(pcie, nvme0n1):
    # get pm register
    assert None != pcie.cap_offset(1)
    pm_offset = pcie.cap_offset(1)
    pmcs = pcie[pm_offset+4]
    assert pcie.power_state == 0

    # set d3hot
    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)

    # and exit d3hot
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    # again
    pcie.power_state = 0
    logging.info("curent power state: %d" % pcie.power_state)
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.power_state == 0
    

def test_pcie_aspm_l1_and_d3hot(pcie, nvme0n1):
    pcie.aspm = 2
    assert pcie.aspm == 2
    pcie.power_state = 3
    time.sleep(1)
    pcie.power_state = 0
    pcie.aspm = 0
    assert pcie.aspm == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()

    pcie.power_state = 3
    assert pcie.power_state == 3
    pcie.aspm = 2
    time.sleep(1)
    pcie.aspm = 0
    assert pcie.aspm == 0
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()
    assert pcie.aspm == 0

    pcie.power_state = 3
    assert pcie.power_state == 3
    time.sleep(1)
    pcie.power_state = 0
    assert pcie.power_state == 0
    nvme0n1.ioworker(io_size=2, time=2).start().close()


    
