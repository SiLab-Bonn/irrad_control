import serial
import logging
import time


class ArduinoFreqCount(object):
    """Class to read from Arduino temperature sensor setup"""

    # Command references
    cmds = {'get_frequency': 'gf',
            'get_samplingtime': 'gt',
            'set_samplingitme': 'st',
            'failure_cmd': 'fh'}


    #I guess still need to write get_raw_frequency and get samplingtime
    def __init__(self, port="/dev/ttyACM0", baudrate=9600, timeout=5):

        #super() hilft bei mehrfach vererbung
        super(ArduinoFreqCount, self).__init__()

        # Make nice serial interface
        self.interface = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        time.sleep(2)  # Sleep to allow Arduino to reboot caused by serial connection

        # Check connection by writing invalid data and receiving answer
        # Could this be any invalid data?
        self.interface.write(self.cmds['failure_cmd'].encode())
        test_res = float(self.interface.readline().strip())

        if test_res == 9876543:
            print('yes')
            logging.debug("Serial connection to Arduino temperature sensor established.")
        else:
            logging.error("No reply on serial connection to Arduino FreqCounter.")

    def get_samplingtime(self):
        """Gets the samplingtime of the Arduino"""
        cmd = self.cmds['get_samplingtime']
        self.interface.write(cmd.encode())
        samplingtime = self.interface.read()
        
        print(samplingtime)

        return samplingtime

    def get_frequency(self):
        """Gets the current frequency"""
        cmd = self.cmds['get_frequency']
        self.interface.write(cmd.encode())
        frequency = self.interface.read()
        print(frequency)
        return frequency



    def get_temp(self, sensor):
        """Gets temperature of sensor where 0 <= sensor <= 7 is the physical pin number of the sensor on
        the Arduino analog pin. Can also be a list of ints."""

        # Make int sensors to list
        sensor = sensor if isinstance(sensor, list) else [sensor]

        # Create string to send via serial which will return respective temperatures
        cmd = ''.join(['{}{}'.format(self.cmd_delimiter, s) for s in sensor]).encode()

        # Send via serial interface
        self.interface.write(cmd)

        # Get result; make sure we get the correct amount of results
        res = [999] * len(sensor)
        for i in range(len(sensor)):
            try:
                res[i] = float(self.interface.readline().strip())
            # Timeout of readline returned empty string which cannot be converted to float
            except ValueError:
                logging.error("Timeout for reading of temperature sensor {}.".format(sensor[i]))

        # Make return dict
        temp_data = dict(zip(sensor, res))

        # Check results;
        for j in range(len(res)):
            if res[j] == 999:  # 999 is error code from Arduino firmware
                logging.error("Temperature sensor {} could not be read.".format(sensor[j]))
                del temp_data[sensor[j]]

            # If we're not in the correct temperature region
            elif not self.ntc_lim[0] <= res[j] <= self.ntc_lim[1]:
                temp = 'low' if res[j] < self.ntc_lim[0] else 'high'
                msg = "Temperature sensor {} reads extremely {} temperature. Is the thermistor connected correctly?".format(sensor[j], temp)
                logging.warning(msg)

        return temp_data
