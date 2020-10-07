#! /usr/bin/env python
import logging
import os
import unittest

import astropy.units as u
import numpy as np

import pint.toa as t
import pint.models as m
from pinttestdata import datadir


class TestOrbitPhase(unittest.TestCase):
    """Test orbital phase calculations"""

    @classmethod
    def setUpClass(cls):
        os.chdir(datadir)
        cls.pJ1855 = "B1855+09_NANOGrav_dfg+12_modified_DD.par"
        cls.mJ1855 = m.get_model(cls.pJ1855)
        cls.pJ0737 = "0737A_latest.par"
        cls.mJ0737 = m.get_model(cls.pJ0737)
        cls.timfile = "test1.tim"
        cls.toas = t.get_TOAs(cls.timfile)

    def test_J1855_nonzero_ecc(self):
        log = logging.getLogger("TestJ1855_nonzero_ecc")
        ts = self.mJ1855.T0.value + np.linspace(0, self.mJ1855.PB.value, 101)
        self.mJ1855.ECC.value = 0.1  # set the eccentricity to zero
        phs = self.mJ1855.orbital_phase(ts, anom="mean")
        assert np.all(phs.value >= 0), "Not all phases >= 0"
        assert np.all(phs.value <= 2 * np.pi), "Not all phases <= 2*pi"
        phs2 = self.mJ1855.orbital_phase([ts[0], ts[49]], anom="ecc")
        assert phs2[0] == phs[0], "Eccen anom != Mean anom"
        assert phs2[1] != phs[49], "Eccen anom == Mean anom"
        phs3 = self.mJ1855.orbital_phase([ts[0], ts[49]], anom="true")
        assert phs3[0] == phs[0], "Eccen anom != True anom"
        assert phs3[1] != phs[49], "Eccen anom == True anom"

    def test_J1855_zero_ecc(self):
        log = logging.getLogger("TestJ1855_zero_ecc")
        self.mJ1855.ECC.value = 0.0  # set the eccentricity to zero
        self.mJ1855.OM.value = 0.0  # set omega to zero
        phs1 = self.mJ1855.orbital_phase(self.mJ1855.T0.value, anom="mean")
        assert phs1.value == 0.0, "Mean anom != 0.0 at T0"
        phs1 = self.mJ1855.orbital_phase(self.mJ1855.T0.value + 0.1, anom="mean")
        phs2 = self.mJ1855.orbital_phase(self.mJ1855.T0.value + 0.1, anom="ecc")
        assert phs2 == phs1, "Eccen anom != Mean anom"
        phs3 = self.mJ1855.orbital_phase(self.mJ1855.T0.value + 0.1, anom="true")
        assert phs3 == phs1, "True anom != Mean anom"

    def test_J0737(self):
        log = logging.getLogger("TestJ0737")
        # The following is a conjunction time as confirmed by Shapiro delay
        nu = self.mJ0737.orbital_phase(55586.296434515, anom="true").value
        omega = self.mJ0737.components["BinaryDD"].binary_instance.omega().value
        # Conjunction occurs when nu + OM == 90 deg
        assert np.isclose(
            np.degrees(np.fmod(nu + omega, 2 * np.pi)), 90.0
        ), "J0737 conjunction time is bad"
