import logging
from bitstring import CreationError
from time import time
from serial import SerialException

# Package imports
from irrad_control.devices import devices
from irrad_control.utils.daq_proc import DAQProcess
from irrad_control.devices.motorstage.base_axis import BaseAxis, BaseAxisTracker
from irrad_control.utils.dut_scan import DUTScan
from irrad_control.devices.readout import RO_DEVICES


class IrradServer(DAQProcess):
    """Implements a server process which controls the DAQ and XYStage"""

    def __init__(self, name=None):

        # Set name of this interpreter process
        name = 'server' if name is None else name

        # Hold server devices
        self.devices = {}

        # Call init of super class
        super(IrradServer, self).__init__(name=name)

    def _start_server(self, setup):
        """Sets up the server process"""

        # Update setup
        self.server = setup['server']
        self.setup = setup['setup']

        # Overwrite server setup with our server
        self.setup['server'] = self.setup['server'][self.server]

        # Setup logging
        self._setup_logging()

        self._init_devices()

        self._setup_devices()

        self._launch_daq_threads()

    def _init_devices(self):

        # Dict holding potentially shared ports which connect to multi-device controllers
        shared_ports = {}

        # When ever a BaseAxis device is initialized, we want to track the movement
        self.axis_tracker = BaseAxisTracker(context=self.context,
                                            address=self._internal_sub_addr,
                                            sender=self.name)

        # Loop over server devices and initialize
        for dev in self.setup['server']['devices']:

            try:

                # Get device and init kwargs
                device = getattr(devices, dev)
                init_kwargs = self.setup['server']['devices'][dev]['init']

                # Check if device is Zaber motorstage which potentially shares port through multi controller
                if issubclass(device, (devices.ZaberStepAxis, devices.ZaberMultiAxis)):
                    port = init_kwargs['port']
                    # Check if port has been opened
                    if port not in shared_ports:
                        shared_ports[port] = devices.ZaberAsciiPort(port)
                    init_kwargs['port'] = shared_ports[port]

                # Actually initialize device
                if isinstance(init_kwargs, dict):
                    self.devices[dev] = device(**init_kwargs)
                else:
                    self.devices[dev] = device()

                # If device is BaseAxis, track movement
                if isinstance(self.devices[dev], BaseAxis):
                    self.axis_tracker.track_axis(axis=self.devices[dev], axis_id=0, axis_domain=dev)

                elif hasattr(self.devices[dev], 'axis'):
                    for axis_id, a in enumerate(self.devices[dev].axis):
                        if isinstance(a, BaseAxis):
                            self.axis_tracker.track_axis(axis=a, axis_id=axis_id, axis_domain=dev)

            except (IOError, SerialException, CreationError) as e:

                if type(e) is SerialException:
                    msg = "Could not connect to serial port {}. Maybe it is used by another process?"

                    if 'port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['port']
                    elif 'serial_port' in self.setup['server']['devices'][dev]['init']:
                        port = self.setup['server']['devices'][dev]['init']['serial_port']
                    else:
                        port = 'unknown'

                    logging.error(msg.format(port))
                elif type(e) is CreationError:
                    logging.error("Could not find DAQBoard on I2C bus")
                else:
                    if dev == 'ADCBoard':
                        logging.error("Could not access SPI device file. Enable SPI interface!")

                logging.warning("{} removed from server devices".format(dev))

                if dev in self.commands:
                    del self.commands[dev]

    def _setup_devices(self):

        ### Specific device-related procedures ###

        if 'ADCBoard' in self.devices:
            self.devices['ADCBoard'].drate = self.setup['server']['readout']['sampling_rate']
            self.devices['ADCBoard'].setup_channels(self.setup['server']['readout']['ch_numbers'])

        if 'ScanStage' in self.devices:

            self.dut_scan = DUTScan(scan_stage=self.devices['ScanStage'])
            self.dut_scan.setup_zmq(ctx=self.context, skt=self.socket_type['data'], addr=self._internal_sub_addr,
                                    sender=self.server)

        if 'IrradDAQBoard' in self.devices and self.setup['server']['readout']['device'] == RO_DEVICES.DAQBoard:
            # Set initial ro scales
            self.devices['IrradDAQBoard'].set_ifs(group='sem',
                                                  ifs=self.setup['server']['readout']['ro_group_scales']['sem'])
            self.devices['IrradDAQBoard'].set_ifs(group='ch12',
                                                  ifs=self.setup['server']['readout']['ro_group_scales']['ch12'])

            if 'ntc' in self.setup['server']['readout']:
                ntc_channels = [int(ntc) for ntc in self.setup['server']['readout']['ntc']]
                self.devices['IrradDAQBoard'].cycle_temp_channels(channels=ntc_channels, timeout=0.2)

    def daq_thread(self, daq_func):
        """
        Does data acquisition in separate thread, retrieving results and putting them into the outgoing queue
        """

        internal_data_pub = self.create_internal_data_pub()

        # Acquire data if not stop signal is set
        while not self.stop_flags['send'].is_set():

            meta, data = daq_func()

            # Put data into outgoing queue
            internal_data_pub.send_json({'meta': meta, 'data': data})

    def _launch_daq_threads(self):

        for dev in self.devices:

            # Start data sending thread
            if dev == 'ADCBoard':
                self.launch_thread(target=self.daq_thread, daq_func=self._daq_adc)

            elif dev == 'ArduinoTempSens':
                self.launch_thread(target=self.daq_thread, daq_func=self._daq_temp)

    def _daq_adc(self):
        """
        Does data acquisition of ADC
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'raw_data'}

        _data = self.devices['ADCBoard'].read_channels(self.setup['server']['readout']['channels'])

        # If we're using the NTC readout of the DAqBoard
        if 'IrradDAQBoard' in self.devices and 'ntc' in self.setup['server']['readout']:
            # Expect the temp channel only to be changed programmatically
            _meta['ntc_ch'] = self.devices['IrradDAQBoard'].get_temp_channel(cached=True)

        return _meta, _data

    def _daq_temp(self):
        """
        Does data acquisition in separate thread by reading the temp values and putting the result into the outgoing queue
        """

        # Add meta data and data
        _meta = {'timestamp': time(), 'name': self.server, 'type': 'temp'}

        temp_setup = self.setup['server']['devices']['ArduinoTempSens']['setup']

        # Read raw temp data
        raw_temp = self.devices['ArduinoTempSens'].get_temp(sorted(temp_setup.keys()))

        _data = dict([(temp_setup[sens], raw_temp[sens]) for sens in raw_temp])

        return _meta, _data

    def handle_cmd(self, target, cmd, data=None):
        """Handle all commands. After every command a reply must be send."""

        # Handle server commands
        if target == 'server':

            if cmd == 'start':

                # Start server with setup which is cmd data
                self._start_server(data)
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=self.pid)

            elif cmd == 'shutdown':
                self.shutdown()

        elif target == 'ro_board':

            ro_board = self.devices['IrradDAQBoard']

            if cmd == 'set_ifs':
                ro_board.set_ifs(group=data['group'], ifs=data['ifs'])
                _data = {'group': data['group'], 'ifs': ro_board.get_ifs(group=data['group'])}
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)
            elif cmd == 'get_ifs':
                _data = {'group': data['group'], 'ifs': ro_board.get_ifs(group=data['group'])}
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)
            elif cmd == 'set_temp_ch':
                if ro_board.is_cycling_temp_channels():
                    ro_board.stop_cycle_temp_channels()
                ro_board.set_temp_channel(channel=data['ch'])
            elif cmd == 'cycle_temp_chs':
                ro_board.cycle_temp_channels(channels=data['chs'], timeout=data['timeout'])
            elif cmd == 'set_gpio':
                ro_board.gpio_value = data['val']
            elif cmd == 'get_gpio':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=ro_board.gpio_value)

        elif target == 'stage':

            xy_stage = self.devices['ZaberXYStage']

            if cmd == 'move_rel':

                xy_stage.axis[0 if data['axis'] == 'x' else 1].move_rel(value=data['distance'], unit=data['unit'])

                _data = [axis.get_position(unit='mm') for axis in xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'move_abs':

                xy_stage.axis[0 if data['axis'] == 'x' else 1].move_abs(value=data['distance'], unit=data['unit'])

                _data = [axis.get_position(unit='mm') for axis in xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_speed':

                xy_stage.axis[0 if data['axis'] == 'x' else 1].set_speed(value=data['speed'], unit=data['unit'])

                _data = [axis.get_speed(unit='mm/s') for axis in xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'set_range':

                xy_stage.axis[0 if data['axis'] == 'x' else 1].set_range(value=data['range'], unit=data['unit'])

                _data = [axis.get_range(unit='mm') for axis in xy_stage.axis]

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'prepare':
                self.dut_scan.setup_scan(**data)
                _data = {'n_rows': self.dut_scan.scan_config['n_rows'], 'rows': self.dut_scan.scan_config['rows']}

                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'scan':

                self.dut_scan.scan_device()

            elif cmd == 'stop':
                if not self.dut_scan.event('stop'):
                    self.dut_scan.event('stop', True)

            elif cmd == 'finish':
                if not self.dut_scan.event('finish'):
                    self.dut_scan.event('finish', True)

            elif cmd == 'pos':
                _data = [axis.get_position(unit='mm') for axis in xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_pos':
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=xy_stage.config[0]['positions'])  #FIXME!!!

            elif cmd == 'add_pos':
                xy_stage.add_position(**data)

            elif cmd == 'del_pos':
                xy_stage.remove_position(data)

            elif cmd == 'move_pos':
                xy_stage.move_to_position(**data)

            elif cmd == 'get_speed':
                _data = [axis.get_speed(unit='mm/s') for axis in xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'get_range':
                _data = [axis.get_range(unit='mm') for axis in xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'home':
                xy_stage.home_stage()
                _data = [axis.get_position(unit='mm') for axis in xy_stage.axis]
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=_data)

            elif cmd == 'no_beam':
                if data:
                    if not self.dut_scan.event('no_beam'):
                        self.dut_scan.event('no_beam', True)
                else:
                    if not self.dut_scan.event('no_beam'):
                        self.dut_scan.event('no_beam', False)
                self._send_reply(reply=cmd, _type='STANDARD', sender=target, data=data)

    def clean_up(self):
        """Mandatory clean up - method"""
        try:
            del self.xy_stage
        except AttributeError:
            pass


def main():

    irrad_server = IrradServer()
    irrad_server.start()
    irrad_server.join()


if __name__ == '__main__':
    main()
