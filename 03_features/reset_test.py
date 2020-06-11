import pytest
import logging

from nvme import Controller, Namespace, Buffer, Qpair, Pcie, Subsystem
from scripts.psd import IOCQ, IOSQ, PRP, PRPList, SQE, CQE


# PCIe, different of power states and resets
def test_power_and_reset(pcie, nvme0, subsystem):
    pcie.aspm = 2              # ASPM L1
    pcie.power_state = 3       # PCI PM D3hot
    pcie.aspm = 0
    pcie.power_state = 0

    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    pcie.reset()               # PCIe reset: hot reset, TS1, TS2
    nvme0.reset()              # reset controller after pcie reset
    nvme0.getfeatures(7).waitdone()

    subsystem.reset()          # NVMe subsystem reset: NSSR
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    subsystem.power_cycle(10)  # power cycle NVMe device: cold reset
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

    subsystem.poweroff()
    subsystem.poweron()
    nvme0.reset()              # controller reset: CC.EN
    nvme0.getfeatures(7).waitdone()

