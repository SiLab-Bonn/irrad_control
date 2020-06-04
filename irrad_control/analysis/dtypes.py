"""Collection of dtypes for numpy structured arrays used within the analysis / interpretation"""
from copy import deepcopy


# Timestamps are 8 byte floats
_timestamp = '<f8'

# Raw data type; needs to be extended according to amount of ADC channels
_raw = [('timestamp', _timestamp)]

# Beam data type: contains info about beamm current and position from primary and secondary signals
_beam = [('timestamp', '<f8'),  # Timestamp of current measurement [s]
         ('current', '<f4'),  # Beam current value [A]
         ('current_err', '<f4'),  # Error of the beam current e.g. measurement error [A]
         ('current_secondary', '<f4'),  # Beam current value calculated from secondary signals e.g. digital [A]
         ('current_err_secondary', '<f4'),  # Error of the beam current calculated from secondary signals e.g. measurement error [A]
         ('position_x', '<f4'),  # Relative x position of the mean of the beam distribution [%]
         ('position_y', '<f4'),  # Relative y position of the mean of the beam distribution [%]
         ('position_x_secondary', '<f4'),  # Relative x position of the mean of the beam distribution from secondary signals [%]
         ('position_y_secondary', '<f4')]  # Relative x position of the mean of the beam distribution from secondary signals[%]

# Fluence data type: contains the data gathered while scanning samples through the particle beam.
_fluence = [('timestamp_start', _timestamp),  # Posix-timestamp when beginning to scan a row [s]
            ('timestamp_stop', _timestamp),  # Posix-timestamp when ending to scan a row [s]
            ('scan', '<i4'),  # Number of *completed* scans
            ('row', '<i4'),  # Number of currently-scanned row
            ('mean_beam_current', '<f4'),  # Mean of the beam current during scanning current row [nA]
            ('mean_beam_current_err', '<f4'),  # Error of the beam current; quadratic addition of std of beam current and measurement error [nA]
            ('scan_speed', '<f4'),  # Speed with which the sample is scanned [mm/s]
            ('scan_step', '<f4'),  # Step size e.g. the spacing in between scanned rows [mm]
            ('proton_fluence', _timestamp),  # Mean of the proton fluence during scanning current row [protons/cm^2]
            ('proton_fluence_err', _timestamp),  # Error of the proton fluence determined from beam current measurement error [neutrons/cm^2]
            ('neutron_fluence', _timestamp),  # Mean of the neutron equivalent fluence during scanning current row [protons/cm^2]
            ('neutron_fluence_err', _timestamp),  # Error of the neutron equivalent fluence determined from beam current measurement error [neutrons/cm^2]
            ('x_start', '<f4'),  # x component of the starting position of currently-scanned row
            ('y_start', '<f4'),  # y component of the starting position of currently-scanned row
            ('x_stop', '<f4'),  # x component of the stopping position of currently-scanned row
            ('y_stop', '<f4')]  # y component of the stopping position of currently-scanned row

# Result data type: contains proton as well as neutron fluence and scaling factor
_result = [('proton_fluence', _timestamp),
           ('proton_fluence_err', _timestamp),
           ('neutron_fluence', _timestamp),
           ('neutron_fluence_err', _timestamp),
           ('hardness_factor', '<f4'),
           ('hardness_factor_err', '<f4')]

# Historgram data types
_hist = [('histogram', '<u4'),
         ('bins_x', '<u2'),
         ('bins_y', '<u2')]


class CopyDict(dict):
    """Dictionary that returns a copy of its field instead of pointer to object"""
    def __init__(self):
        super(CopyDict, self).__init__()

    def __getitem__(self, item):
        return deepcopy(super(CopyDict, self).__getitem__(item))


IRRAD_DTYPES = CopyDict()

# Write to the dictionary
IRRAD_DTYPES['RAW'] = _raw
IRRAD_DTYPES['BEAM'] = _beam
IRRAD_DTYPES['FLUENCE'] = _fluence
IRRAD_DTYPES['RESULT'] = _result
IRRAD_DTYPES['HIST'] = _hist
IRRAD_DTYPES['TIMESTAMP'] = _timestamp
