"""
This is a demo of how to remove pyaps delay using PyAPS
Usage: first run pyrate/scripts/run_prepifg.py using your config file
Then use the command:

"""
__author__ = 'Sudipta Basak'
__date_created__ = '4/02/16'
import PyAPS as pa
import numpy as np
import sys
import os
import re
import glob2
from osgeo import gdalconst, gdal
from pyrate import config as cf
from pyrate import ifgconstants as ifc
from pyrate import prepifg
from pyrate import gamma


PYRATEPATH = os.environ['PYRATEPATH']
ECMWF_DIR = os.path.join(PYRATEPATH, 'ECMWF')
ECMWF_PRE = 'ERA-Int_'
ECMWF_EXT = '_12.grib'  # TODO: build dynamically with closest available grib
APS_STATUS = 'REMOVED'
GEOTIFF = 'GEOTIFF'
ECMWF = 'ECMWF'


def remove_aps_delay(ifgs, params):
    def get_incidence_map2():
        if params[cf.APS_INCIDENCE_MAP] is not None:
            incidence_map = get_incidence_map()
        else:  # elevation map was provided
            assert params[cf.APS_ELEVATION_MAP] is not None
            incidence_map = get_incidence_map()
        return incidence_map

    def get_incidence_map():
        """
        :param incidence_map:
        :param params:
        :param inc_or_ele: 1 when incidence map, 0 when elevation map
        :return:
        """
        if params[cf.APS_ELEVATION_MAP] is not None:
            f, e = os.path.basename(params[cf.APS_ELEVATION_MAP]).split(
                '.')
        else:
            f, e = os.path.basename(params[cf.APS_INCIDENCE_MAP]).split(
                '.')
        multilooked = os.path.join(
            params[cf.OUT_DIR],
            f + '_' + e +
            '_{looks}rlks_{crop}cr.tif'.format(
                looks=params[cf.IFG_LKSX],
                crop=params[
                    cf.IFG_CROP_OPT]))
        assert os.path.exists(multilooked), \
            'cropped and multilooked incidence map file not found. ' \
            'Use apsmethod=1, Or run prepifg with gamma processor'
        ds = gdal.Open(multilooked, gdalconst.GA_ReadOnly)
        if params[cf.APS_INCIDENCE_MAP] is not None:
            incidence_map = ds.ReadAsArray()
        else:
            incidence_map = 90 - ds.ReadAsArray()
        ds = None  # close file
        return incidence_map

    lat, lon, nx, ny, dem, mlooked_dem = read_dem(params)
    dem_header = (lon, lat, nx, ny)

    incidence_angle = None
    incidence_map = get_incidence_map2()
    list_of_dates_for_grb_download = []
    for ifg in ifgs:  # demo for only one ifg
        if params[cf.PROCESSOR] == 1:  # gamma
            PTN = re.compile(r'\d{8}')
            date_pair = [i for i in PTN.findall(os.path.basename(ifg.data_path))]
        elif params[cf.PROCESSOR] == 0:  # roipac
            # adding 20 to dates here, so dates before 2000 won't work
            # TODO: fix pre 2000 dates
            PTN = re.compile(r'\d{6}')
            date_pair = ['20' + i for i in
                         PTN.findall(os.path.basename(ifg.data_path))]
        else:
            raise AttributeError('processor needs to be gamma(1) or roipac(0)')

        list_of_dates_for_grb_download += date_pair

        first_grb = os.path.join(ECMWF_DIR,
                                 ECMWF_PRE + date_pair[0] + ECMWF_EXT)
        second_grb = os.path.join(ECMWF_DIR,
                                  ECMWF_PRE + date_pair[1] + ECMWF_EXT)

        # download .grb file if does not exist
        if not (os.path.exists(first_grb) and os.path.exists(second_grb)):
            # download weather files at 12:00 UTC (other options 00:00, 06:00, 18:00)
            pa.ecmwf_download(date_pair, '12', 'ECMWF')

        # rdr_correction(date_pair)

        # TODO: lat lon correction when lat and lon files are available
        # aps1.getgeodelay(phs1, inc=23.0, wvl=0.056,
        #   lat=os.path.join(PYAPS_EXAMPLES, 'lat.flt'),
        #   lon=os.path.join(PYAPS_EXAMPLES, 'lon.flt'))
        # aps2.getgeodelay(phs2, inc=23.0, wvl=0.056,
        #   lat=os.path.join(PYAPS_EXAMPLES, 'lat.flt'),
        #   lon=os.path.join(PYAPS_EXAMPLES, 'lon.flt'))
        # LLphs = phs2-phs1
        # print dem_header, mlooked_dem
        if params[cf.APS_METHOD] == 1:
            # no need to calculate incidence angle for all ifgs, they are the same
            if incidence_angle is None:
                incidence_angle = get_incidence_angle(date_pair, params)
            aps_delay = geo_correction(date_pair, mlooked_dem, dem_header, dem,
                                       incidence_angle)
        elif params[cf.APS_METHOD] == 2:
            # no need to calculate incidence map for all ifgs, they are the same
            aps_delay = geo_correction(date_pair, mlooked_dem, dem_header, dem,
                                       incidence_map)
        else:
            raise APSException('APS method must be 1 or 2')


        ifg.phase_data -= aps_delay  # remove delay
        # add it to the meta_data dict
        ifg.meta_data[ifc.PYRATE_APS_ERROR] = APS_STATUS
        # write meta_data to file
        ifg.dataset.SetMetadataItem(ifc.PYRATE_APS_ERROR, APS_STATUS)

        ifg.write_modified_phase()


def rdr_correction(date_pair):
    """ using rdr coordinates to remove APS """
    raise NotImplementedError("This has not been implemented yet for PyRate")
    # aps1 = pa.PyAPS_rdr(
    #     os.path.join(ECMWF_DIR, ECMWF_PRE + date_pair[0] + ECMWF_EXT),
    #     SYD_TEST_DEM_ROIPAC, grib='ECMWF', verb=True,
    #     demfmt='HGT', demtype=np.int16)
    # aps2 = pa.PyAPS_rdr(
    #     os.path.join(ECMWF_DIR, ECMWF_PRE + date_pair[1] + ECMWF_EXT),
    #     SYD_TEST_DEM_ROIPAC, grib='ECMWF', verb=True,
    #     demfmt='HGT', demtype=np.int16)
    # phs1 = np.zeros((aps1.ny, aps1.nx))
    # phs2 = np.zeros((aps2.ny, aps2.nx))
    # print 'Without Lat Lon files'
    # # using random incidence angle
    # aps1.getdelay(phs1, inc=23.0)
    # aps2.getdelay(phs2, inc=23.0)
    # aps_delay = phs2 - phs1  # delay in meters as we don't provide wavelength
    # return aps_delay


def geo_correction(date_pair, mlooked_dem, dem_header, dem,
                   incidence_angle_or_map):

    """ using geo coordinates to remove APS """

    aps1 = pa.PyAPS_geo(
        os.path.join(ECMWF_DIR, ECMWF_PRE + date_pair[0] + ECMWF_EXT),
        mlooked_dem, grib=ECMWF, verb=True,
        demfmt=GEOTIFF, demtype=np.float32, dem_header=dem_header)
    aps2 = pa.PyAPS_geo(
        os.path.join(ECMWF_DIR, ECMWF_PRE + date_pair[1] + ECMWF_EXT),
        mlooked_dem, grib=ECMWF, verb=True,
        demfmt=GEOTIFF, demtype=np.float32, dem_header=dem_header)
    phs1 = np.zeros((aps1.ny, aps1.nx))
    phs2 = np.zeros((aps2.ny, aps2.nx))
    print 'Without Lat Lon files'
    aps1.getdelay_pyrate(phs1, dem, inc=incidence_angle_or_map)
    aps2.getdelay_pyrate(phs2, dem, inc=incidence_angle_or_map)
    aps_delay = phs2 - phs1  # delay in meters as we don't provide wavelength
    return aps_delay


def read_dem(params):
    dem_file = params[cf.DEM_FILE]
    geotif_dem = os.path.join(
        params[cf.OUT_DIR], os.path.basename(dem_file).split('.')[0] + '.tif')
    mlooked_dem = prepifg.mlooked_path(geotif_dem,
                                       looks=params[cf.IFG_LKSX],
                                       crop_out=params[cf.IFG_CROP_OPT])
    # make sure mlooked dem exist
    if not os.path.exists(mlooked_dem):
        raise prepifg.PreprocessError('mlooked dem was not found.'
                                      'Please run prepifg.')
    dem_header = gamma.parse_dem_header(params[cf.DEM_HEADER_FILE])
    lat, lon, nx, ny = return_pyaps_lat_lon(dem_header)

    ds = gdal.Open(mlooked_dem, gdalconst.GA_ReadOnly)
    dem = ds.ReadAsArray()
    ds = None
    return lat, lon, nx, ny, dem, mlooked_dem


def get_incidence_angle(date_pair, params):
    # incidence angle exists in unw header files, not in dem
    SLC_DIR = params[cf.SLC_DIR] if params[cf.SLC_DIR] else \
        params[cf.OBS_DIR]
    header_path = glob2.glob(os.path.join(
        SLC_DIR, '**/*%s*slc.par' % date_pair[0]))[0]
    header = gamma.parse_epoch_header(header_path)
    incidence_angle = header[ifc.INCIDENCE_ANGLE]
    return incidence_angle


def return_pyaps_lat_lon(dem_header):
    nx, ny = dem_header[ifc.PYRATE_NCOLS], dem_header[ifc.PYRATE_NROWS]
    lat = np.zeros((2, 1))
    lon = np.zeros((2, 1))
    lat[1] = dem_header[ifc.PYRATE_LAT]
    lon[0] = dem_header[ifc.PYRATE_LONG]
    if lon[0] < 0:
        lon[0] += 360.0
    dx = np.float(dem_header[ifc.PYRATE_X_STEP])
    dy = np.float(dem_header[ifc.PYRATE_Y_STEP])
    lat[0] = lat[1] + dy * ny
    lon[1] = lon[0] + dx * nx
    return lat, lon, nx, ny


class APSException(Exception):
    """
    generic exception class for APS correction
    """
    pass