import logging
from threading import Thread, Event
import time
import yaml
from zaber.serial import *
from collections import OrderedDict
from functools import wraps
from irrad_control import xy_stage_config, xy_stage_config_yaml


def movement_tracker(movement_func):
    """
    Decorator function which is used keep track of the stage travel. Optionally publishes movement data via ZMQ.

    Parameters
    ----------
    movement_func: function object
        function which executes a stage movement

    Returns
    -------
    movement_wrapper: function object
        wrapped movement_func
    """
    @wraps(movement_func)
    def movement_wrapper(self, target, axis, unit=None):

        # Axis index and name
        axis_idx = 0 if axis is self.x_axis else 1
        axis_name = 'x' if axis is self.x_axis else 'y'

        # Get current position in meters
        start = self.steps_to_distance(self.position[axis_idx], unit='m')

        if self._zmq_setup:

            # Publish collection of data from which movement can be predicted
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'stage'}
            _data = {'status': 'move_start', 'pos': start, 'axis': axis_idx, 'unit': unit,
                     'speed': self.get_speed(axis, unit='m/s'),
                     'accel': self.get_accel(axis, unit='m/s2'),
                     'range': self.get_range(axis, unit='m')}

            # Publish data
            self._move_pub.send_json({'meta': _meta, 'data': _data})

        # Execute movement
        reply = movement_func(self, target, axis, unit)

        # Get position after movement
        stop = self.steps_to_distance(self.position[axis_idx], unit='m')

        # Calculate distance travelled in meter
        travel = abs(stop - start)

        if self._zmq_setup:

            # Publish collection of data from which movement can be predicted
            _meta = {'timestamp': time.time(), 'name': self.zmq_config['sender'], 'type': 'stage'}
            _data = {'status': 'move_stop', 'pos': stop, 'axis': axis_idx, 'travel': travel, 'unit': unit}

            # Publish data
            self._move_pub.send_json({'meta': _meta, 'data': _data})

        # Update interval and total travel
        self.config['interval_travel'][axis_name] += travel
        self.config['total_travel'][axis_name] += travel

        if self.config['interval_travel'][axis_name] >= self.config['maintenance_interval']:
            self.config['interval_travel'][axis_name] = 0
            logging.warning("{}-axis of XY-stage reached service interval travel! "
                            "See https://www.zaber.com/wiki/Manuals/X-LRQ-E#Precautions".format(axis_name))

        self.config['last_update'] = time.asctime()

        return reply

    return movement_wrapper


class ZaberXYStage(object):
    """Class for interfacing the Zaber XY-stage of the irradiation setup at Bonn isochronous cyclotron"""

    def __init__(self, serial_port='/dev/ttyUSB0'):
        """
        Define the attributes of this Zaber stage. For information please refer to the following links:
        https://www.zaber.com/products/xy-xyz-gantry-systems/XY/details/X-XY-LRQ300BL-E01/features
        https://www.zaber.com/products/linear-stages/X-LRQ-E/details/X-LRQ300BL-E01

        Parameters
        ----------
        serial_port : str
            String holding the serial port to which the stage is connected
        """

        # Exact model of stage at irradiation site
        self.model = 'X-XY-LRQ300BL-E01-KX14C-SQ3'

        # Important parameters of each stage
        self.microstep = 0.49609375e-6  # meter
        self.linear_motion_per_rev = 6.35e-3  # meter
        self.steps_per_rev = 200  # steps

        # Initialize the zaber device
        port = AsciiSerial(serial_port)

        # Devices
        self.x_device = AsciiDevice(port, 1)
        self.y_device = AsciiDevice(port, 2)

        # Axes
        self.x_axis = self.x_device.axis(1)
        self.y_axis = self.y_device.axis(1)

        # Travel ranges in microsteps
        self.x_range_steps = [int(self.x_axis.send("get limit.min").data), int(self.x_axis.send("get limit.max").data)]
        self.y_range_steps = [int(self.y_axis.send("get limit.min").data), int(self.y_axis.send("get limit.max").data)]

        # Current position of stage in mm; always holds the position in steps and is updated after movement
        self.position = self.get_position()

        # Attributes related to scanning
        self.scan_params = {}  # Dict to hold relevant scan parameters
        self.stop_scan = Event()  # Event to stop scan
        self.finish_scan = Event()  # Event to finish a scan after completing all rows of current iteration
        self.pause_scan = Event()  # Event to wait while scanning if e.g. beam current is low or beam is shut off

        # Units
        self.dist_units = OrderedDict([('mm', 1.0), ('cm', 1e1), ('m', 1e3)])
        self.speed_units = OrderedDict([('mm/s', 1.0), ('cm/s', 1e1), ('m/s', 1e3)])
        self.accel_units = OrderedDict([('mm/s2', 1.0), ('cm/s2', 1e1), ('m/s2', 1e3)])

        # Set speeds on both axis to reasonable values: 10 mm / s
        self.set_speed(10, self.x_axis, unit='mm/s')
        self.set_speed(10, self.y_axis, unit='mm/s')

        # Attributes related to ZMQ data publishing
        self.zmq_config = {}
        self._move_pub = None
        self._zmq_setup = False

        # XY Stage config
        self.config = xy_stage_config
        
    def __del__(self):
        """Store the current configuration on deletion and close socket if ZMQ was set up"""
        self.save_config()
        # Close socket
        if self._zmq_setup:
            self._move_pub.close()

    def setup_zmq(self, ctx, skt, addr, sender=None):
        """
        Method to pass a ZMQ context to the stage class in order to allow it to publish data on a socket

        Parameters
        ----------
        ctx: zmq.Context instance
            A ZMQ context instance from which sockets can be created
        skt: zmq.PUB
            A ZMQ publisher socket
        addr: str
            A ZMQ address to connect to. Must be a valid combination of protocol, address and port
        sender: str, None
            Name of the device from which the stage is interfaced
        """

        if not hasattr(ctx, 'socket'):
            raise ValueError("ZMQ context instance must have 'socket' method")

        if not isinstance(skt, int):
            raise ValueError("ZMQ socket type must be of type 'int'")

        if not isinstance(addr, str):
            raise ValueError("ZMQ address must be of type 'str'")

        # Make publisher for movements
        self._move_pub = ctx.socket(skt)
        self._move_pub.set_hwm(10)
        self._move_pub.connect(addr)

        # Store
        self.zmq_config.update({'ctx': ctx, 'skt': skt, 'addr': addr, 'sender': sender})

        # Set flag
        self._zmq_setup = True

    def _check_reply(self, reply):
        """Method to check the reply of a command which has been issued to one of the axes"""

        # Get reply data and corresponding axis
        msg = "{}-axis: {}".format('x' if reply.device_address == 1 else 'y', reply.data)

        # Flags are either 'OK' or 'RJ'
        if reply.reply_flag != 'OK':
            logging.error("Command rejected by {}".format(msg))
            return False

        # Use logging to debug
        logging.debug("Command succeeded: {}".format(msg))
        return True

    def _check_unit(self, unit, target_units):
        """Checks whether *unit* is in *target_units*."""

        # Check if unit is okay
        if unit not in target_units.keys():
            logging.warning("Unit of speed must be one of '{}'. Using {}!".format(', '.join(target_units.keys()),
                                                                                  target_units.keys()[0]))
            unit = target_units.keys()[0]

        return unit

    def home_stage(self):
        """Home entire stage"""
        _reply = (self.home_y_axis(), self.home_x_axis())
        return _reply

    def home_x_axis(self):
        """Move x axis to the home position and check and return reply"""
        return self.move_absolute(self.x_range_steps[0], self.x_axis)

    def home_y_axis(self):
        """Move y axis to the home position and check and return reply. y is inverted"""
        return self.move_absolute(self.y_range_steps[-1], self.y_axis)

    def speed_to_step_s(self, speed, unit="mm/s"):
        """
        Method to convert *speed* given in *unit* into micro steps per second

        Parameters
        ----------
        speed : float
            speed in *unit* to be converted to micro steps per second
        unit : str
            unit from which speed should be converted. Must be in self.speed_units
        """

        # Check if unit is okay
        unit = self._check_unit(unit, self.speed_units)

        # Return result as integer; for conversion formula see: https://zaber.com/documents/ZaberSpeedSetting.xls
        return int(self.speed_units[unit] * speed * 1.6384 * 1e-3 * 1.0 / self.microstep)

    def speed_to_unit(self, speed, unit='mm/s'):
        """
        Convert integer speed in steps per second to some unit in self.speed_units

        Parameters
        ----------
        speed : int
            speed in micro steps per second
        unit : str
            unit in which speed should be converted. Must be in self.speed_units.
        """

        # Check if unit is okay
        unit = self._check_unit(unit, self.speed_units)

        # Return result as float; for conversion formula see: https://zaber.com/documents/ZaberSpeedSetting.xls
        return float(1.0 / self.speed_units[unit] * speed / 1.6384 * 1e3 * self.microstep)

    def set_speed(self, speed, axis, unit='mm/s'):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        speed : float
            speed at which *axis* should move
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which speed is given. Must be in self.speed_units. If None, set speed in steps / s
        """

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        # If unit is given, get speed in steps
        speed = speed if unit is None else self.speed_to_step_s(speed, unit)

        # Get maxspeed of current axis
        _axis_maxspeed = int(axis.send("get resolution").data) * 16384

        # Check whether speed is not larger than maxspeed
        if speed > _axis_maxspeed:
            msg = "Maximum speed of this axis is {} mm/s. Speed not updated!".format(self.speed_to_unit(_axis_maxspeed))
            logging.warning(msg)
            return

        # Issue command and wait for reply and check
        _reply = axis.send("set maxspeed {}".format(speed))
        self._check_reply(_reply)

        return _reply

    def get_speed(self, axis, unit='mm/s'):
        """
        Get the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which speed should be converted. Must be in self.speed_units. If None, return speed in steps / s
        """

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        # Issue command and wait for reply and check
        _reply = axis.send("get maxspeed")
        success = self._check_reply(_reply)

        # Get speed in steps per second; 0 if command didn't succeed
        speed = 0 if not success else int(_reply.data)

        return speed if unit is None else self.speed_to_unit(speed, unit)

    def get_position(self, unit=None):
        """
        Returns the current position of the XY-stage in given unit

        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        unit = unit if unit is None else self._check_unit(unit, self.dist_units)

        pos = [x.get_position() for x in (self.x_axis, self.y_axis)]

        pos[1] = int(300e-3 / self.microstep) - pos[1]  # Physical max. travel range is 300 mm == 604724 * self.microstep

        pos = pos if unit is None else [self.steps_to_distance(r, unit) for r in pos]

        return pos

    def set_range(self, _range, axis, unit='mm'):
        """
        Set the speed at which axis moves for move rel and move abs commands

        Parameters
        ----------
        _range : iterable
            range to be set, must be of len 2
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which range is given. Must be in self.dist_units. If None, set speed in steps
        """

        if len(_range) != 2:
            logging.warning("Range must be 2-element iterable containing lower and upper limit. Abort")
            return

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        _replies = [axis.send("set limit.min {}".format(_range[0] if unit is None else self.distance_to_steps(distance=_range[0], unit=unit))),
                    axis.send("set limit.max {}".format(_range[1] if unit is None else self.distance_to_steps(distance=_range[1], unit=unit)))]

        for _reply in _replies:
            self._check_reply(_reply)

        # Update
        # Travel ranges in microsteps
        self.x_range_steps = self.get_range(self.x_axis, unit=None)
        self.y_range_steps = self.get_range(self.y_axis, unit=None)

        return _replies

    def get_range(self, axis, unit='mm'):
        """
        Get the travel range of axis

        Parameters
        ----------
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which range should be converted. Must be in self.dist_units. If None, return speed in steps
        """

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        # Issue command and wait for reply and check
        _replies = [axis.send("get limit.min"), axis.send("get limit.max")]
        success = [self._check_reply(_reply) for _reply in _replies]

        # Get speed in steps per second; 0 if command didn't succeed
        _range = [0 if not success[i] else int(_reply.data) for i, _reply in enumerate(_replies)]

        unit = unit if unit is None else self._check_unit(unit, self.dist_units)

        return _range if unit is None else [self.steps_to_distance(r, unit) for r in _range]

    def accel_to_step_s2(self, accel, unit="mm/s2"):
        """
        Method to convert acceleration *accel* given in *unit* into micro steps per square second

        Parameters
        ----------
        accel : float
            acceleration in *unit* to be converted to micro steps per square second
        unit : str
            unit from which acceleration should be converted. Must be in self.accel_units
        """

        # Check if unit is sane; if it checks out, return same unit, else returns smallest available unit
        unit = self._check_unit(unit, self.accel_units)

        # Return result as integer; for conversion formula see: https://zaber.com/documents/ZaberSpeedSetting.xls
        return int(self.accel_units[unit] * accel * 1.6384 * 1e-7 * 1.0 / self.microstep)

    def accel_to_unit(self, accel, unit='mm/s2'):
        """
        Method to convert acceleration *accel* given in micro steps per square second into *unit*

        Parameters
        ----------
        accel : int
            acceleration in micro steps per square second
        unit : str
            unit in which acceleration should be converted. Must be in self.accel_units
        """

        # Check if unit is sane; if it checks out, return same unit, else returns smallest available unit
        unit = self._check_unit(unit, self.accel_units)

        # Return result as float; for conversion formula see: https://zaber.com/documents/ZaberSpeedSetting.xls
        return float(1.0 / self.accel_units[unit] * accel / 1.6384 * 1e7 * self.microstep)

    def set_accel(self, accel, axis, unit='mm/s2'):
        """
        Set the acceleration at which the axis increases speed for move rel and move abs commands

        Parameters
        ----------
        accel : float, int
            acceleration; float if *unit* is given, else integer in steps
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which distance is given. Must be in self.dist_units. If None, get acceleration in steps / s^2
        """

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        # If unit is given, get acceleration in steps
        accel = accel if unit is None else self.accel_to_step_s2(accel, unit)

        _max_accel = 32767

        # Check whether speed is not larger than maxspeed
        if accel > _max_accel:
            msg = "Maximum acceleration of this axis is {} m/s^2." \
                  "Acceleration not updated!".format(self.accel_to_unit(_max_accel, 'm/s2'))
            logging.warning(msg)
            return

        # Issue command and wait for reply and check
        _reply = axis.send("set accel {}".format(accel))
        self._check_reply(_reply)

        return _reply

    def get_accel(self, axis, unit='mm/s2'):
        """
        Get the acceleration at which the axis increases speed for move rel and move abs commands

        Parameters
        ----------
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : str, None
            unit in which acceleration should be converted. Must be in self.accel_units.
            If None, get acceleration in steps / s^2
        """

        # Check if axis is known
        if axis not in (self.x_axis, self.y_axis):
            logging.warning("Unknown axis. Abort.")
            return

        # Issue command and wait for reply and check
        _reply = axis.send("get accel")
        success = self._check_reply(_reply)

        # Get acceleration in steps per square second; 0 if command didn't succeed
        accel = 0 if not success else int(_reply.data)

        return accel if unit is None else self.accel_to_unit(accel, unit)

    def calc_accel(self, speed, distance):
        """
        Returns acceleration needed to get to *speed* in *distance*

        Parameters
        ----------
        speed : float
            speed which should be matched in *distance*
        distance : float
            distance to travel
        """

        return speed**2.0 / (2.0 * distance)

    def distance_to_steps(self, distance, unit="mm"):
        """
        Method to convert a *distance* given in *unit* into micro steps

        Parameters
        ----------
        distance : float
            distance of travel
        unit : str
            unit in which distance is given. Must be in self.dist_units
        """

        # Check if unit is sane; if it checks out, return same unit, else returns smallest available unit
        unit = self._check_unit(unit, self.dist_units)

        return int(self.dist_units[unit] / 1e3 * distance / self.microstep)

    def steps_to_distance(self, steps, unit="mm"):
        """
        Method to convert a *steps* given in distance given in *unit*

        Parameters
        ----------
        steps : int
            distance in steps or position in steps
        unit : str
            unit in which distance is given. Must be in self.dist_units
        """

        # Check if unit is sane; if it checks out, return same unit, else returns smallest available unit
        unit = self._check_unit(unit, self.dist_units)

        return float(steps * self.microstep * 1e3 / self.dist_units[unit])

    @movement_tracker
    def move_relative(self, target, axis, unit=None):
        """
        Method to move either in vertical or horizontal direction relative to the current position.
        Does sanity check on travel destination and axis

        Parameters
        ----------
        target : float, int
            distance of relative travel
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : None, str
            unit in which target is given. Must be in self.dist_units. If None, interpret as steps
        """

        # Get distance in steps
        dist_steps = target if unit is None else self.distance_to_steps(target, unit)

        # Get current position
        curr_pos = axis.get_position()

        # Get minimum and maximum steps of travel
        min_step, max_step = int(axis.send("get limit.min").data), int(axis.send("get limit.max").data)

        # Vertical axis is inverted; multiply with distance with -1
        if axis is self.y_axis:
            dist_steps *= -1

        # Check whether there's still room to move
        if not min_step <= curr_pos + dist_steps <= max_step:
            logging.error("Movement out of travel range. Abort!")
            return

        # Send command to axis and return reply
        _reply = axis.move_rel(dist_steps)
        self._check_reply(_reply)

        # Update position
        self.position = self.get_position()

        return _reply

    @movement_tracker
    def move_absolute(self, target, axis, unit=None):
        """
        Method to move along the given axis to the absolute position

        Parameters
        ----------
        target : float, int
            position to which will be travelled in steps or float with a unit
        axis : zaber.serial.AsciiAxis
            either self.x_axis or self.y_axis
        unit : None, str
            unit in which target is given. Must be in self.dist_units. If None, interpret as steps
        """

        # Get position in steps
        pos_steps = target if unit is None else self.distance_to_steps(target, unit)

        # Get minimum and maximum steps of travel
        min_step, max_step = int(axis.send("get limit.min").data), int(axis.send("get limit.max").data)

        # Check whether there's still room to move
        if not min_step <= pos_steps <= max_step:
            logging.error("Movement out of travel range. Abort!")
            return

        # Send command to axis and return reply
        _reply = axis.move_abs(pos_steps)
        self._check_reply(_reply)

        # Update position
        self.position = self.get_position()

        return _reply

    def move_to_position(self, x=None, y=None, unit=None, name=None):
        """
        Method which moves the stage to a given position: Position can either be defined by giving *x* and *y* values
        with a *unit* or a *name*. If a *name* is given, it must be contained in the self.config['positions']. If a
        a name as well as x and y values are given, the name is prioritized.

        Parameters
        ----------
        x: float, int
            x value of the position given in *unit*
        y: float, int
            y value of the position given in *unit*
        unit: str, None
             string of unit to use. Must be in self.dist_units. If None, x and y must be integers and the unit is interpreted as steps
        name: str
            name of position in self.config['positions'] to travel to
        """

        if name is None and any(val is None for val in (x, y)):
            raise ValueError("Either the 'x' and 'y' arguments or the name of the position have to be given")

        # If we're moving to an already known position
        if name is not None:

            # Check if position is in config
            if name not in self.config['positions']:
                raise KeyError("Position '{}' not in known position: {}".format(name, ', '.join(n for n in self.config['positions'])))

            # Update values
            x, y, unit = [self.config['positions'][name][k] for k in ('x', 'y', 'unit')]

        # I'm ashamed
        # FIXME: start using ncoder bit to invert y axis instead of coding like trhe first human
        m_dist = self.steps_to_distance(int(300e-3 / self.microstep), unit=unit)
        y = m_dist - y

        # Do the movement; first move x, then y axis
        self.move_absolute(x, self.x_axis, unit=unit)
        self.move_absolute(y, self.y_axis, unit=unit)

    def add_position(self, name, x, y, unit, date=None):
        """
        Method which stores new XY stage position in the config. If it already exists in self.config['positions'], the entries are updated

        Parameters
        ----------
        name: str
            name of the position
        x: float
            x position
        y: float
            y position
        unit: str
            string of metric unit
        date: str, None
            if None, will be return value of time.asctime()
        """

        # Position info dict
        new_pos = {'x': x, 'y': y, 'unit': unit, 'date': time.asctime() if date is None else date}

        # We're updating an existing position
        if name in self.config['positions']:

            logging.debug('Updating position {} (Last update {})'.format(name, self.config['positions'][name]['date']))

            # Update directly in dict
            self.config['positions'][name].update(new_pos)

        # We're adding a new position
        else:

            logging.debug('Adding position {}!'.format(name))

            self.config['positions'][name] = new_pos

    def remove_position(self, name):
        """
        Method which removes an existing XY stage position from self.config['positions']

        Parameters
        ----------
        name: str
            name of the position
        """

        if name in self.config['positions']:
            del self.config['positions'][name]
        else:
            logging.warning('Position {} unknown and therefore cannot be removed.'.format(name))

    def save_config(self):
        """
        Method save the content of self.config aka irrad_control.xy_stage_config to the respective config yaml (overwriting it).
        This method get's called inside the instances' destructor.
        """

        try:
            logging.info('Updating XY-Stage positions')

            # Overwrite xy stage stats
            with open(xy_stage_config_yaml, 'w') as _xys_w:
                yaml.safe_dump(self.config, _xys_w, default_flow_style=False)

            logging.info('Successfully updated XY-Stage configuration')

        except (OSError, IOError):
            logging.warning("Could not update XY-Stage configuration file at {}. Maybe it is opened by another process?".format(xy_stage_config_yaml))

    def prepare_scan(self, rel_start_point, rel_end_point, scan_speed, step_size, server):
        """
        Prepares a scan by storing all needed info in self.scan_params

        Parameters
        ----------
        rel_start_point : tuple, list
            iterable of starting point (x [mm], y [mm]) relative to current position, defining upper left corner of area
        rel_end_point : tuple, list
            iterable of end point (x [mm], y [mm]) relative to current position, defining lower right corner of area
        scan_speed : float
            horizontal scan speed in mm / s
        step_size : float
            step size of vertical steps in mm
        server : str
            IP address of server which controls the stage
        """

        # Store position which is used as origin of relative coordinate system for scan
        self.scan_params['origin'] = (self.x_axis.get_position(), self.y_axis.get_position())

        # Store starting scan position
        self.scan_params['start_pos'] = (self.scan_params['origin'][0] - self.distance_to_steps(rel_start_point[0]),
                                         # inverted y-axis
                                         self.scan_params['origin'][1] + self.distance_to_steps(rel_start_point[1]))

        # Store end position of scan
        self.scan_params['end_pos'] = (self.scan_params['origin'][0] - self.distance_to_steps(rel_end_point[0]),
                                       # inverted y-axis
                                       self.scan_params['origin'][1] + self.distance_to_steps(rel_end_point[1]))

        # Store input args
        self.scan_params['speed'] = scan_speed
        self.scan_params['step_size'] = step_size
        self.scan_params['server'] = server

        # Calculate number of rows for the scan
        dy = self.distance_to_steps(step_size, unit='mm')
        self.scan_params['n_rows'] = int(abs(self.scan_params['end_pos'][1] - self.scan_params['start_pos'][1]) / dy)

        # Make dictionary with absolute position (in steps) of each row
        rows = [(row, self.scan_params['start_pos'][1] - row * dy) for row in range(self.scan_params['n_rows'])]
        self.scan_params['rows'] = dict(rows)

    def _check_scan(self, scan_params):
        """
        Method to do sanity checks on the *scan_params* dict.

        Parameters
        ----------
        scan_params : dict
            dict containing all the info for doing a scan of a rectangular area.
            If *scan_params* is None, use instance attribute self.scan_params instead.
        """

        # Check if dict is empty or not dict
        if not scan_params or not isinstance(scan_params, dict):
            msg = "Scan parameter dict is empty or not of type dictionary! " \
                  "Try using prepare_scan method or fill missing info in dict. Abort."
            logging.error(msg)
            return False

        # Check if scan_params dict contains all necessary info
        scan_reqs = ('origin', 'start_pos', 'end_pos', 'n_rows', 'rows', 'speed', 'step_size', 'server')
        missed_reqs = [req for req in scan_reqs if req not in scan_params]

        # Return if info is missing
        if missed_reqs:
            msg = "Scan parameter dict is missing required info: {}. " \
                  "Try using prepare_scan method or fill missing info in dict. Abort.".format(', '.join(missed_reqs))
            logging.error(msg)
            return False

        return True

    def scan_row(self, row, speed=None, scan_params=None):
        """
        Method to scan a single row of a device. Uses info about scan parameters from scan_params dict.
        Does sanity checks. The actual scan is done in a separate thread which calls self._scan_row.

        Parameters
        ----------
        row : int:
            Integer of row which should be scanned
        speed : float, None
            Scan speed in mm/s or None. If None, current speed of x-axis is used for scanning
        scan_params : dict
            dict containing all the info for doing a scan of a rectangular area.
            If *scan_params* is None, use instance attribute self.scan_params instead.
        """

        # Scan parameters dict; if None, use instance attribute self.scan_params
        scan_params = scan_params if scan_params is not None else self.scan_params

        # Check input dict
        if not self._check_scan(scan_params):
            return

        # Check row is in scan_params['rows']
        if row not in scan_params['rows']:
            msg = "Row {} is not in known rows starting from {} to {}. Abort".format(row,
                                                                                     min(scan_params['rows'].keys()),
                                                                                     max(scan_params['rows'].keys()))
            logging.error(msg)
            return

        # Start scan in separate thread
        scan_thread = Thread(target=self._scan_row, args=(row, scan_params, speed))
        scan_thread.start()

    def scan_device(self, scan_params=None):
        """
        Method to scan a rectangular area by stepping vertically with fixed step size and moving with
        fixed speed horizontally. Uses info about scan parameters from scan_params dict. Does sanity checks.
        The actual scan is done in a separate thread which calls self._scan_device.

        Parameters
        ----------
        scan_params : dict
            dict containing all the info for doing a scan of a rectangular area.
            If *scan_params* is None, use instance attribute self.scan_params instead.
        """

        # Scan parameters dict; if None, use instance attribute self.scan_params
        scan_params = scan_params if scan_params is not None else self.scan_params

        # Check input dict
        if not self._check_scan(scan_params):
            return

        # Start scan in separate thread
        scan_thread = Thread(target=self._scan_device, args=(scan_params, ))
        scan_thread.start()

    def _scan_row(self, row, scan_params, speed=None, scan=-1, data_pub=None):
        """
        Method which is called by self._scan_device or self.scan_row. See docstrings there.

        Parameters
        ----------
        row : int
            Row to scan
        scan_params : dict
            dict containing all the info for doing a scan of a rectangular area.
        speed : float, None
            Scan speed in mm/s or None. If None, current speed of x-axis is used for scanning
        scan : int
            Integer indicating the scan number during self.scan_device. *scan* for single rows is -1
        data_pub : zmq socket, None
            Socket on which data is published. If None, check if a socket can be created, if not, no data is published
        """

        # Check socket, if no socket is given and ZMQ is setup for this instance, open one
        socket_close = data_pub is None and self._zmq_setup is True

        # If we're closing the socket, we have to open one before
        if socket_close:
            data_pub = self.zmq_config['ctx'].socket(self.zmq_config['skt'])
            data_pub.set_hwm(10)
            data_pub.connect(self.zmq_config['addr'])

        # Check whether this method is called from within self.scan_device or single row is scanned.
        # If single row is scanned, we're coming from
        from_origin = (self.x_axis.get_position(), self.y_axis.get_position()) == scan_params['origin']

        if speed is not None:
            self.set_speed(speed, self.x_axis, unit='mm/s')

        # Make x start and end variables
        x_start, x_end = scan_params['start_pos'][0], scan_params['end_pos'][0]

        # Check whether we are scanning from origin
        if from_origin:
            x_reply = self.move_absolute(x_start, self.x_axis)

            # Check reply; if something went wrong raise error
            if not self._check_reply(x_reply):
                msg = "X-axis did not move to start point. Abort"
                raise UnexpectedReplyError(msg)

        # Move to the current row
        y_reply = self.move_absolute(scan_params['rows'][row], self.y_axis)

        # Check reply; if something went wrong raise error
        if not self._check_reply(y_reply):
            msg = "Y-axis did not move to row {}. Abort.".format(row)
            raise UnexpectedReplyError(msg)

        # Publish if we have a socket
        if data_pub is not None:

            # Publish data
            _meta = {'timestamp': time.time(), 'name': scan_params['server'], 'type': 'stage'}
            _data = {'status': 'scan_start', 'scan': scan, 'row': row,
                     'speed': self.get_speed(self.x_axis, unit='mm/s'),
                     'x_start': self.steps_to_distance(self.position[0], unit='mm'),
                     'y_start': self.steps_to_distance(self.position[1], unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        # Scan the current row
        x_reply = self.move_absolute(x_end if self.x_axis.get_position() == x_start else x_start, self.x_axis)

        # Check reply; if something went wrong raise error
        if not self._check_reply(x_reply):
            msg = "X-axis did not scan row {}. Abort.".format(row)
            raise UnexpectedReplyError(msg)

        # Publish if we have a socket
        if data_pub is not None:

            # Publish stop data
            _meta = {'timestamp': time.time(), 'name': scan_params['server'], 'type': 'stage'}
            _data = {'status': 'scan_stop',
                     'x_stop': self.steps_to_distance(self.position[0], unit='mm'),
                     'y_stop': self.steps_to_distance(self.position[1], unit='mm')}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

        if socket_close:
            data_pub.close()

        if from_origin:
            # Move back to origin; move y first in order to not scan over device
            self.move_absolute(scan_params['origin'][1], self.y_axis)
            self.move_absolute(scan_params['origin'][0], self.x_axis)

    def _scan_device(self, scan_params):
        """
        Method which is supposed to be called by self.scan_device. See docstring there.

        Parameters
        ----------
        scan_params : dict
            dict containing all the info for doing a scan of a rectangular area.
        """

        # initialize zmq data publisher
        data_pub = self.zmq_config['ctx'].socket(self.zmq_config['skt'])
        data_pub.set_hwm(10)
        data_pub.connect(self.zmq_config['addr'])

        # Move to start point
        self.move_absolute(scan_params['start_pos'][0], self.x_axis)
        self.move_absolute(scan_params['start_pos'][1], self.y_axis)

        # Set the scan speed
        self.set_speed(scan_params['speed'], self.x_axis, unit='mm/s')

        # Initialize scan
        _meta = {'timestamp': time.time(), 'name': scan_params['server'], 'type': 'stage'}
        _data = {'status': 'scan_init', 'y_step': scan_params['step_size'], 'n_rows': scan_params['n_rows']}

        # Put init data
        data_pub.send_json({'meta': _meta, 'data': _data})

        try:

            # Loop until fluence is reached and self.stop_scan event is set
            # Each scan is counted as one coverage of the entire area
            scan = 0
            while not (self.stop_scan.wait(1e-1) or self.finish_scan.wait(1e-1)):

                # Determine whether we're going from top to bottom or opposite
                _tmp_rows = list(range(scan_params['n_rows']) if scan % 2 == 0 else reversed(range(scan_params['n_rows'])))

                # Loop over rows
                for row in _tmp_rows:

                    # Check for emergency stop; if so, raise error
                    if self.stop_scan.wait(1e-1):
                        msg = "Scan was stopped manually"
                        raise UnexpectedReplyError(msg)

                    # Wait for beam current to be sufficient / beam to be on for scan
                    while self.pause_scan.wait(1e-1):
                        msg = "Low beam current or no beam in row {} of scan {}. " \
                              "Waiting for beam current to rise.".format(row, scan)
                        logging.warning(msg)
                        time.sleep(1)

                        # If beam does not recover and we need to stop manually
                        if self.stop_scan.wait(1e-1):
                            msg = "Scan was stopped manually"
                            raise UnexpectedReplyError(msg)

                    # Scan row
                    self._scan_row(row=row, scan_params=scan_params, scan=scan, data_pub=data_pub)

                # Increment
                scan += 1

        # Some axis command didn't succeed or emergency exit was issued
        except UnexpectedReplyError:
            logging.exception("Scan aborted!")
            pass

        finally:

            # Put finished data
            _meta = {'timestamp': time.time(), 'name': scan_params['server'], 'type': 'stage'}
            _data = {'status': 'scan_finished'}

            # Publish data
            data_pub.send_json({'meta': _meta, 'data': _data})

            # Reset speeds
            self.set_speed(10, self.x_axis, unit='mm/s')
            self.set_speed(10, self.y_axis, unit='mm/s')

            # Move back to origin; move y first in order to not scan over device
            self.move_absolute(scan_params['origin'][1], self.y_axis)
            self.move_absolute(scan_params['origin'][0], self.x_axis)

            # Reset signal so one can scan again
            if self.stop_scan.is_set():
                self.stop_scan.clear()

            if self.finish_scan.is_set():
                self.finish_scan.clear()

            if self.pause_scan.is_set():
                self.pause_scan.clear()

            data_pub.close()
