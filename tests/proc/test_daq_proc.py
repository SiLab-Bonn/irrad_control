import os
import time
import logging
import unittest

from irrad_control import config_path
from irrad_control.utils.tools import load_yaml
from irrad_control.utils.daq_proc import DAQProcess


class BaseDAQProcess(DAQProcess):

    def __init__(self):
        super(BaseDAQProcess, self).__init__(name='TestDAQProcess', commands={})

    # Define clean up
    def clean_up(self):
        pass


class TestDAQProcess(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Create process
        cls.daq_proc = BaseDAQProcess()

        # Launch process
        cls.daq_proc.start()

        # Wait until process is created with irrad.pid file
        start = time.time()
        while not os.path.isfile(os.path.join(config_path, '.irrad.pid')):
            time.sleep(0.2)

            # Wait max 5 seconds
            if time.time() - start > 5:
                break

    @classmethod
    def tearDownClass(cls):
        # Send SIGTERM
        cls.daq_proc.terminate()

        # Wait until down
        cls.daq_proc.join()

        # Check pid file is gone
        assert not os.path.isfile(os.path.join(config_path, '.irrad.pid'))

    def test_pid_file_content(self):

        pid_file_content = load_yaml(os.path.join(config_path, '.irrad.pid'))

        # Check that it is not empty
        assert pid_file_content

        # Check that values are is not empty
        assert all(pid_file_content.values())

        # Check that all ports are found
        assert all(isinstance(port, int) for port in pid_file_content['ports'].values())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDAQProcess)
    unittest.TextTestRunner(verbosity=2).run(suite)
