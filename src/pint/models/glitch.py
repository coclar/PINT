"""Pulsar timing glitches."""
# glitch.py
# Defines glitch timing model class
from __future__ import absolute_import, division, print_function

import astropy.units as u
import numpy as np

from pint import dimensionless_cycles
from pint.models.parameter import prefixParameter
from pint.models.timing_model import MissingParameter, PhaseComponent
from pint.utils import split_prefixed_name


class Glitch(PhaseComponent):
    """Pulsar spin-down glitches."""

    register = True
    category = 'glitch'

    def __init__(self):
        super(Glitch, self).__init__()

        self.add_param(prefixParameter(name="GLPH_1", units="pulse phase",
                       value=0.0,
                       descriptionTplt=lambda x: "Phase change for glitch %d"
                                                 % x,
                       unitTplt=lambda x: 'pulse phase',
                       type_match='float'))
        # FIXME: should this be long double?
        self.add_param(prefixParameter(name="GLEP_1", units='day',
                       descriptionTplt=lambda x: "Epoch of glitch %d" % x,
                       unitTplt=lambda x: 'day',
                       type_match='MJD', time_scale='tdb'))
        self.add_param(prefixParameter(name="GLF0_1", units="Hz", value=0.0,
                       descriptionTplt=lambda x: "Permanent frequency change"
                                                 " for glitch %d" % x,
                       unitTplt=lambda x: 'Hz',
                       type_match='float'))
        self.add_param(prefixParameter(name="GLF1_1", units="Hz/s", value=0.0,
                       descriptionTplt=lambda x: "Permanent frequency-"
                                                 "derivative change for glitch"
                                                 " %d " % x,
                       unitTplt=lambda x: 'Hz/s'))
        self.add_param(prefixParameter(name="GLF2_1", units="Hz/s^2", value=0.,
                       descriptionTplt=lambda x: "Permanent second frequency-"
                                                 "derivative change for glitch"
                                                 " %d " % x,
                       unitTplt=lambda x: 'Hz/s^2'))
        self.add_param(prefixParameter(name="GLF0D_1", units="Hz", value=0.0,
                       descriptionTplt=lambda x: "Decaying frequency change "
                                                 "for glitch %d " % x,
                       unitTplt=lambda x: 'Hz',
                       type_match='float'))

        self.add_param(prefixParameter(name="GLTD_1",
                       units="day", value=0.0,
                       descriptionTplt=lambda x: "Decay time constant for"
                                                 " glitch %d" % x,
                       unitTplt=lambda x: 'day',
                       type_match='float'))
        self.phase_funcs_component += [self.glitch_phase]

    def setup(self):
        super(Glitch, self).setup()
        # Check for required glitch epochs, set not specified parameters to 0
        self.glitch_prop = ['GLPH_', 'GLF0_', 'GLF1_', 'GLF2_',
                            'GLF0D_', 'GLTD_']
        self.glitch_indices = [getattr(self, y).index for x in self.glitch_prop
                               for y in self.params if x in y]
        for idx in set(self.glitch_indices):
            if not hasattr(self, 'GLEP_%d' % idx):
                msg = 'Glicth Epoch is needed for Glicth %d.' % idx
                raise MissingParameter("Glitch", 'GLEP_%d' % idx, msg)
            for param in self.glitch_prop:
                if not hasattr(self, param + '%d' % idx):
                    param0 = getattr(self, param + '1')
                    self.add_param(param0.new_param(idx))
                    getattr(self, param + '%d' % idx).value = 0.0
                self.register_deriv_funcs(getattr(self, \
                     'd_phase_d_'+param[0:-1]), param + '%d' % idx)

        # Check the Decay Term.
        glf0dparams = [x for x in self.params if x.startswith('GLF0D_')]
        for glf0dnm in glf0dparams:
            glf0d = getattr(self, glf0dnm)
            idx = glf0d.index
            if glf0d.value != 0.0 and \
                    getattr(self, "GLTD_%d" % idx).value == 0.0:
                msg = "None zero GLF0D_%d parameter needs a none" \
                      " zero GLTD_%d parameter" % (idx, idx)
                raise MissingParameter("Glitch", 'GLTD_%d' % idx, msg)

    def print_par(self):
        result = ''
        for idx in set(self.glitch_indices):
            for param in ['GLEP_',] + self.glitch_prop:
                par = getattr(self, param + '%d'%idx)
                result += par.as_parfile_line()
        return result

    def glitch_phase(self, toas, delay):
        """Glitch phase function.
        delay is the time delay from the TOA to time of pulse emission
        at the pulsar, in seconds.
        returns an array of phases in long double
        """
        tbl = toas.table
        phs = np.zeros_like(tbl, dtype=np.longdouble) * u.cycle
        glepnames = [x for x in self.params if x.startswith('GLEP_')]
        with u.set_enabled_equivalencies(dimensionless_cycles):
            for glepnm in glepnames:
                glep = getattr(self, glepnm)
                eph = glep.value
                idx = glep.index
                dphs = getattr(self, "GLPH_%d" % idx).quantity
                dF0 = getattr(self, "GLF0_%d" % idx).quantity
                dF1 = getattr(self, "GLF1_%d" % idx).quantity
                dF2 = getattr(self, "GLF2_%d" % idx).quantity
                dt = (tbl['tdbld'] - eph) * u.day - delay
                dt = dt.to(u.second)
                affected = dt > 0.0  # TOAs affected by glitch
                # decay term
                dF0D = getattr(self, "GLF0D_%d" % idx).quantity
                if dF0D != 0.0:
                    tau = getattr(self, "GLTD_%d" % idx).quantity
                    decayterm = dF0D * tau * (1.0 - np.exp(- (dt[affected]
                                              / tau).to(u.Unit(""))))
                else:
                    decayterm = 0.0

                phs[affected] += dphs + dt[affected] * \
                    (dF0 + 0.5 * dt[affected] * dF1 + \
                     1./6. * dt[affected]*dt[affected] * dF2) + decayterm
            return phs.to(u.cycle)

    def d_phase_d_GLPH(self, toas, param, delay):
        """Calculate the derivative wrt GLPH"""
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLPH_':
            raise ValueError("Can not calculate d_phase_d_GLPH with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLPH = getattr(self, param)
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLPH = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLPH.units
        dpdGLPH[affected] += 1.0 * u.cycle/par_GLPH.units
        return dpdGLPH

    def d_phase_d_GLF0(self, toas, param, delay):
        """Calculate the derivative wrt GLF0"""
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLF0_':
            raise ValueError("Can not calculate d_phase_d_GLF0 with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLF0 = getattr(self, param)
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLF0 = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLF0.units
        with u.set_enabled_equivalencies(dimensionless_cycles):
            dpdGLF0[affected] = dt[affected]
        return dpdGLF0

    def d_phase_d_GLF1(self, toas,  param, delay):
        """Calculate the derivative wrt GLF1"""
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLF1_':
            raise ValueError("Can not calculate d_phase_d_GLF1 with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLF1 = getattr(self, param)
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLF1 = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLF1.units
        with u.set_enabled_equivalencies(dimensionless_cycles):
            dpdGLF1[affected] += np.longdouble(0.5) * dt[affected] * dt[affected]
        return dpdGLF1

    def d_phase_d_GLF2(self, toas,  param, delay):
        """Calculate the derivative wrt GLF1"""
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLF2_':
            raise ValueError("Can not calculate d_phase_d_GLF2 with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLF2 = getattr(self, param)
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLF2 = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLF2.units
        with u.set_enabled_equivalencies(dimensionless_cycles):
            dpdGLF2[affected] += np.longdouble(1.0)/6.0 * dt[affected] * dt[affected] * dt[affected]
        return dpdGLF2

    def d_phase_d_GLF0D(self, toas, param, delay):
        """Calculate the derivative wrt GLF0D
        """
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLF0D_':
            raise ValueError("Can not calculate d_phase_d_GLF0D with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLF0D = getattr(self, param)
        tau = getattr(self, "GLTD_%d" % idv).quantity
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLF0D = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLF0D.units
        with u.set_enabled_equivalencies(dimensionless_cycles):
            dpdGLF0D[affected] += tau * (np.longdouble(1.0) - np.exp(- dt[affected]
                                         / tau))
        return dpdGLF0D

    def d_phase_d_GLTD(self, toas, param, delay):
        """Calculate the derivative wrt GLF0D
        """
        tbl = toas.table
        p, ids, idv = split_prefixed_name(param)
        if p !=  'GLTD_':
            raise ValueError("Can not calculate d_phase_d_GLF0D with respect to %s." % param)
        eph = np.longdouble(getattr(self, "GLEP_" + ids).value)
        par_GLTD = getattr(self, param)
        if par_GLTD.value == 0.0:
            return np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLTD.units
        glf0d = getattr(self, 'GLF0D_'+ids).quantity
        tau = par_GLTD.quantity
        dt = (tbl['tdbld'] - eph) * u.day - delay
        dt = dt.to(u.second)
        affected = np.where(dt > 0.0)[0]
        dpdGLTD = np.zeros(len(tbl), dtype=np.longdouble) * u.cycle/par_GLTD.units
        with u.set_enabled_equivalencies(dimensionless_cycles):
            dpdGLTD[affected] += glf0d * (np.longdouble(1.0) - \
                                 np.exp(- dt[affected] / tau)) + \
                                 glf0d * tau * (-np.exp(- dt[affected] / tau)) * \
                                 dt[affected] / (tau * tau)
        return dpdGLTD
