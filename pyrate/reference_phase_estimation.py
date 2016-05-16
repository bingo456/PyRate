"""
This is a python implementation of the refphsest.m of pirate.
"""
__author__ = 'Sudipta Basak'
__date_created__ = '22/12/15'

import numpy as np
from pyrate import config as cf
from pyrate.shared import nanmedian
import parmap


def estimate_ref_phase(ifgs, params, refpx, refpy):
    """
    :param ifgs: list of interferrograms
    :param params: parameters of the simulation
    :param refpx: reference pixel found by ref pixel method
    :param refpy: reference pixel found by ref pixel method
    :returns:
        :ref_phs: reference phase correction
        :ifgs: reference phase data removed list of ifgs
    """
    number_ifgs = len(ifgs)
    _validate_ifgs(ifgs)

    # set reference phase as the average of the whole image (recommended)
    if int(params[cf.REF_EST_METHOD]) == 1:
        ref_phs = est_ref_phase_method1(ifgs, params)

    elif int(params[cf.REF_EST_METHOD]) == 2:
        ref_phs = est_ref_phase_method2(ifgs, params, refpx, refpy)
    else:
        raise ReferencePhaseError('No such option. Use refest=1 or 2')

    return ref_phs, ifgs


def est_ref_phase_method2(ifgs, params, refpx, refpy):
    ref_phs = np.zeros(len(ifgs))
    half_chip_size = int(np.floor(params[cf.REF_CHIP_SIZE] / 2.0))
    chipsize = 2 * half_chip_size + 1
    thresh = chipsize * chipsize * params[cf.REF_MIN_FRAC]
    phase_data = [i.phase_data for i in ifgs]
    if params[cf.PARALLEL]:
        ref_phs_ret = parmap.map(est_ref_phase_method2_milti, phase_data,
                                 half_chip_size, refpx, refpy, thresh)
        for n, ifg in enumerate(ifgs):
            ref_phs[n] = ref_phs_ret[n][0]
            ifg.phase_data = ref_phs_ret[n][1]
    else:
        ref_phs = np.zeros(len(ifgs))
        for n, ifg in enumerate(ifgs):
            ref_phs[n], ifg.phase_data = \
                est_ref_phase_method2_milti(phase_data[n], half_chip_size,
                                            refpx, refpy, thresh)
    return ref_phs


def est_ref_phase_method2_milti(phase_data, half_chip_size,
                                refpx, refpy, thresh):
    patch = phase_data[
            refpy - half_chip_size: refpy + half_chip_size + 1,
            refpx - half_chip_size: refpx + half_chip_size + 1
            ]
    patch = np.reshape(patch, newshape=(-1, 1), order='F')
    if np.sum(~np.isnan(patch)) < thresh:
        raise ReferencePhaseError('The reference pixel'
                                  'is not in high coherent area!')
    ref_ph = nanmedian(patch)
    phase_data -= ref_ph
    return ref_ph, phase_data


def est_ref_phase_method1(ifgs, params):
    ifg_phase_data_sum = np.zeros(ifgs[0].shape, dtype=np.float64)
    # TODO: revisit as this will likely hit memory limit in NCI
    phase_data = [i.phase_data for i in ifgs]
    for ifg in ifgs:
        ifg_phase_data_sum += ifg.phase_data

    if params[cf.PARALLEL]:
        print "ref phase calculation using multiprocessing"
        ref_phs = np.zeros(len(ifgs))
        ref_phs_ret = parmap.map(est_ref_phase_method1_multi,
                                 phase_data,
                                 ifg_phase_data_sum)
        for n, ifg in enumerate(ifgs):
            ref_phs[n] = ref_phs_ret[n][0]
            ifg.phase_data = ref_phs_ret[n][1]
    else:
        print "ref phase calculation in serial"
        ref_phs = np.zeros(len(ifgs))
        for n, ifg in enumerate(ifgs):
            ref_phs[n], ifg.phase_data = \
                est_ref_phase_method1_multi(ifg.phase_data,
                                            ifg_phase_data_sum)
    return ref_phs


def est_ref_phase_method1_multi(phase_data, ifg_phase_data_sum):
    comp = np.isnan(ifg_phase_data_sum)  # this is the same as in Matlab
    comp = np.ravel(comp, order='F')  # this is the same as in Matlab

    ifgv = np.ravel(phase_data, order='F')
    ifgv[comp == 1] = np.nan
    # reference phase
    ref_ph = nanmedian(ifgv)
    phase_data -= ref_ph
    return ref_ph, phase_data


def _validate_ifgs(ifgs):
    if len(ifgs) < 2:
        raise ReferencePhaseError('Need to provide at least 2 ifgs')


class ReferencePhaseError(Exception):
    """
    Generic class for errors in reference phase estimation.
    """
    pass

if __name__ == "__main__":
    import os
    import shutil
    from subprocess import call

    from pyrate.scripts import run_pyrate
    from pyrate import matlab_mst_kruskal as matlab_mst
    from pyrate.tests.common import SYD_TEST_MATLAB_ORBITAL_DIR, SYD_TEST_OUT

    # start each full test run cleanly
    shutil.rmtree(SYD_TEST_OUT, ignore_errors=True)

    os.makedirs(SYD_TEST_OUT)

    params = cf.get_config_params(
            os.path.join(SYD_TEST_MATLAB_ORBITAL_DIR, 'pyrate_system_test.conf'))

    call(["python", "pyrate/scripts/run_prepifg.py",
          os.path.join(SYD_TEST_MATLAB_ORBITAL_DIR, 'pyrate_system_test.conf')])

    xlks, ylks, crop = run_pyrate.transform_params(params)

    base_ifg_paths = run_pyrate.original_ifg_paths(params[cf.IFG_FILE_LIST])

    dest_paths = run_pyrate.get_dest_paths(base_ifg_paths, crop, params, xlks)

    ifg_instance = matlab_mst.IfgListPyRate(datafiles=dest_paths)

    ifgs = ifg_instance.ifgs
    nan_conversion = int(params[cf.NAN_CONVERSION])
    for i in ifgs:
        i.convert_to_mm()
        i.write_modified_phase()
        if nan_conversion and not i.nan_converted:  # nan conversion happens here in networkx mst
            i.convert_to_nans()

    refx, refy = run_pyrate.find_reference_pixel(ifgs, params)

    if params[cf.ORBITAL_FIT] != 0:
        run_pyrate.remove_orbital_error(ifgs, params)

    ref_phs, ifgs = estimate_ref_phase(ifgs, params, refx, refy)
    print ref_phs
