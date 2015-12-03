'''
CUnittests for linrate.py

.. codeauthor:: Ben Davies
'''

import unittest
from numpy import eye, array, ones, where
from numpy.testing import assert_array_almost_equal
from pyrate.config import LR_PTHRESH, LR_MAXSIG, LR_NSIG
from pyrate.linrate import linear_rate
from pyrate import mst
from pyrate.vcm import cvd, get_vcmt
from pyrate.tests.common import sydney_data_setup, sydney_data_setup_ifg_file_list

# TODO: linear rate code
# 1. replace MST key:value date:date pairs with lists of Ifgs?
# 2.: MG: fake some data for a 1 pixel test of stack()
#     figure out what partial inputs we need to do this as a simple test
# 3. MG is going to check if someome at GA has coded lscov in Py (or C/C++/Fortran??)
#
# MG thinks we'll need:
# 1 all the func args
# 2 a VCM
# 3 the time spans (already in Ifgs?)
# 4 the ifg displacement obs (phase_data)



# class LinearRateTests(unittest.TestCase):
#
#     def test_stack_basic(self):
#         raise NotImplementedError
#
#
#     def test_args(self):
#         raise NotImplementedError("Need sanity tests for args to stack()")

#def default_params():
#    return { LR_PTHRESH : 10, LR_NSIG : 3, LR_MAXSIG : 2 }
LR_PTHRESH = 3
LR_NSIG = 3
LR_MAXSIG = 2


class SinglePixelIfg(object):

    def __init__(self,timespan,phase):
        self.time_span = timespan
        self.phase_data = array([[phase]])


class LinearRateTests(unittest.TestCase):
    """Tests the weighted least squares algorithm for determinining
    the best fitting velocity"""

    def setUp(self):
        phase = [0.5, 3.5, 4, 2.5, 3.5, 1]
        timespan = [0.1, 0.7, 0.8, 0.5, 0.7, 0.2]
        self.ifgs = [SinglePixelIfg(s,p) for s,p in zip(timespan,phase)]

    def test_linear_rate(self):
        # Simple test with one pixel and equal weighting
        exprate = array([[5.0]])
        experr = array([[0.836242010007091]])  # from Matlab Pirate
        expsamp = array([[5]])
        vcm = eye(6, 6)
        mst = ones((6, 1, 1))
        mst[4] = 0
        rate, error, samples = linear_rate(self.ifgs, vcm, LR_PTHRESH,
                                           LR_NSIG, LR_MAXSIG, mst)
        assert_array_almost_equal(rate, exprate)
        assert_array_almost_equal(error, experr)
        assert_array_almost_equal(samples, expsamp)
        
    def test_linear_rate_full(self):
        import numpy as np
        self.ifgs = sydney_data_setup()
        ifgs = self.ifgs
        ifg_file_list = sydney_data_setup_ifg_file_list()

        for i in ifgs:
            # i.phase_data.mean(),
            print np.nanmean(i.phase_data), np.count_nonzero(~np.isnan(i.phase_data)), np.count_nonzero(np.isnan(i.phase_data))
            # print np.nonzero(list(np.nonzero(i.phase_data)))

        mstmat = mst.mst_matrix_ifg_indices_as_boolean_array(self.ifgs)

        from numpy import genfromtxt
        import os
        from os import listdir
        from os.path import isfile, join
        mypath = "/home/sudipta/Dropbox/GA/PyRate/mastmat_csvs"
        onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]

        # my_data = genfromtxt("/home/sudipta/Dropbox/GA/PyRate/mastmat_csvs/mastmat_geo_060619-061002.csv", delimiter=',')

        # for i in range(len(ifgs)):
        #     print np.array_equal(my_data, mstmat[i, :, :])

        for i, f in enumerate(onlyfiles):
            mst_f = genfromtxt(os.path.join(mypath, f), delimiter=',')
            for k, j in enumerate(ifg_file_list):
                # print f.split('mat_')[-1].split('.')[0], os.path.split(j)[-1].split('.')[0]
                if f.split('mat_')[-1].split('.')[0] == os.path.split(j)[-1].split('.')[0]:
                    # print f.split('mat_')[-1], os.path.split(j)[-1]
                    print np.array_equal(mst_f, mstmat[k, :, :])


        # print "self.ifgs[0].phase_data", self.ifgs[0].phase_data
        # print self.ifgs[0]
        # print "mstmat[3,0,0]", mstmat
        # print "mstmat.shape", mstmat.shape

        maxvar = [cvd(i)[0] for i in self.ifgs]
        vcm = get_vcmt(self.ifgs, maxvar)
        # print "vcm", vcm
        # print "vcm.shape", vcm.shape
        # print "maxvar", maxvar
        rate, error, samples = linear_rate(self.ifgs, vcm, LR_PTHRESH,
                                           LR_NSIG, LR_MAXSIG, mstmat)
        # print rate
        #
        # print rate.shape


if __name__ == "__main__":
    unittest.main()
