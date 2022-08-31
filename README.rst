=============================
Irrad_Control |test-status|
=============================

Active Development Location Change
==================================
Development of ``irrad_control`` has moved to the `cyclotron-bonn organization <https://github.com/cyclotron-bonn/irrad_control>`_

Introduction
============

``irrad_control`` is a Python package for data acquisition and control of the proton irradiation site at the 
`Bonn isochronous cyclotron <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/index_EN.html>`_, 
located at the Helmholtz Institut für Strahlen- und Kernphysik (`HISKP <https://www.hiskp.uni-bonn.de/>`_), of Bonn University.
The software features a graphical user interface (GUI), based on `PyQt <https://riverbankcomputing.com/software/pyqt/intro>`_, 
from which the individual setup components can be managed and irradiations can be conducted. Furthermore, the GUI offers online data
visualization of proton beam characteristics and irradiation-specific quantities such as e.g. proton fluence.
The setup control and data acquisition is provided by a (or multiple) Raspberry Pi (RPi) server which is managed by ``irrad_control``,
all acquired data is stored in the binary `HDF5 <https://www.pytables.org/>`_ format. The software furthermore provides a set of analysis methods
for irradiation datasets which produce comprehensive plots.

Installation
============

Due to dependencies, you have to have Python 3.8  with the following packages installed:

- numpy
- pyyaml
- pyzmq
- pytables
- matplotlib
- paramiko
- uncertainties
- tqdm
- numba
- scipy
- pyqt (version 5)
- `pyqtgraph <http://pyqtgraph.org/>`_ (version 0.11)

It's recommended to use a Python environment separate from your system Python. To do so, please install `Miniconda <https://conda.io/miniconda.html>`_.
After installation you can use the package manager ``conda`` to install the required packages. To create a new Python 3.8 environment with the name `irrad`
and required dependencies, type

.. code-block:: bash

   conda create -y -n irrad python=3.8 numpy pyyaml pytables pyzmq pyserial paramiko matplotlib tqdm numba scipy

Run ``conda activate irrad`` to activate the Python environment. To install the required packages that are not available via ``conda``, use ``pip``

.. code-block:: bash

  pip install uncertainties pytest pyqt5==5.12 pyqtgraph==0.11

To finally install & launch ``irrad_control`` run the setup script via

.. code-block:: bash

   pip install -e .

followed by

.. code-block:: bash

   irrad_control

When you start the application you can add RPi servers in the **setup** tab. Each server needs to be set up before usage.
The procedure is explained in the following section.

Quick Setup
============

The data acquisition and control of irradiation setup is done by one (or multiple) Raspberry Pi (RPi) server. Before first usage with `irrad_control`,
each server RPi needs to be aware of the ``ssh key`` of the host PC. Therefore, copy the hosts ``ssh key`` to each RPi server via

.. code-block::

   ssh-copy-id pi@ip-address-of-rpi

where ``ip-address-of-rpi`` is the IP address of the RPi within the network. In case you need to create a ``ssh key`` of the host PC first, you can do so by

.. code-block::

   ssh-keygen -b 2048 -t rsa

After launching ``irrad_control``, you can perform a first-time-setup of the server by adding it via its IP address.
The server is then automatically set up on first use with ``irrad_control``.


Offline Analysis
================

From version v1.3.0 onwards, ``irrad_control`` ships with offline analysis utilities, allowing to analyse e.g. irradiation or calibration data.
The output of ``irrad_control`` are two different file types with the same base name (e.g. ``my_irrad_file``), one containing the configuration (*YAML*) and the other the actual data (*HDF5*).
Both files are required to be present in the same directory.
To analyse irradiation data (e.g. NIEL / TID / fluence) use the ``irrad_analyse`` CLI:

.. code-block:: bash

   irrad_analyse -f my_irrad_file  # No file ending required; --damage (NIEL, TID) is default analysis flag 

which will generate a ``my_irrad_file_analysis_damage.pdf`` output file. Optionally, the ``-o my_custom_output_file.pdf`` option / value pair can be given to give a custom output file name.
To analyse multiple files at once, pass them individually to the `-f` otpion

.. code-block:: bash

   irrad_analyse -f my_irrad_file_0 my_irrad_file_1 my_irrad_file_2
   irrad_analyse -f *.h5  # Analyse all HDF5 files in the current directory

Furthermore, irradiations which were carried out in multiple sessions (e.g. multiple output config / data files) can be analysed by passing the ``--multipart`` flag.
To analyse an multi-file irradiation, pass the list of file base names

.. code-block:: bash

   irrad_analyse -f my_irrad_file_0 my_irrad_file_1 my_irrad_file_2 --multipart
   irrad_analyse -f *.h5 --multipart  # Take all HDF5 files in the current directory

To analyse beam monitor calibration measurements, pass the ``--calibration`` flag.

.. code-block:: bash

   irrad_analyse -f my_calibration_file --calibration
   irrad_analyse -f *.h5 --calibration  # Take all HDF5 files in the current directory

To see the CLI options type

.. code-block:: bash

   irrad_analyse --help

Fluence Distributions
---------------------

1 MeV neutron equivalent fluence distribution with their respective uncertainties, generated by the ``irrad_analyse`` CLI,
from irradiation data of an ITkPixV1 Si-pixel detector, irradiatied to 1e16 neq/cm².

.. list-table::

    * - .. figure:: ../assets/ITkPixV1_1e16_scan_neq_nominal.jpg?raw=true

           1 MeV neutron equivalent fluence, scan area, 1e16 neq/cm²

      - .. figure:: ../assets/ITkPixV1_1e16_scan_neq_error.jpg?raw=true

           1 MeV neutron equivalent fluence uncertainty, scan area, , 1e16 neq/cm²

    * - .. figure:: ../assets/ITkPixV1_1e16_dut_neq_nominal.jpg?raw=true

           1 MeV neutron equivalent fluence, DUT area, , 1e16 neq/ cm²

      - .. figure:: ../assets/ITkPixV1_1e16_dut_neq_error.jpg?raw=true

           1 MeV neutron equivalent fluence uncertainty, DUT area, , 1e16 neq/cm²

Changelog
========

- v1.3.0: Included module for offline analysis of e.g. irradiation data
- v1.2.0: First version with partial support for updated irradiation setup running on Python 3 
- v1.1.0: Deprecated version supporting Python 2/3 as well as deprecated irradiation setup
- v1.0.1: Initial release with semantic verisoning

Documentation
=============

For information on the software structure, data formats and general usage please see the wiki. (TBD)

Proton Irradiation Site
=======================

The proton irradiation site for silicon devices at Bonn University is in operation since early 2020. Typically, a proton beam of 14 MeV kinetic energy, a current of 1 µA and a diameter of a few mm
is used to irradiate devices-under-test (DUTs) in a temperature-controlled box. To achieve homogeneous irradiation, the DUT is scanned through the beam in a row-wise grid, using a two-dimensional 
motorstage. The fluence is determined via online measurement of the beam current at extraction to the DUT during the irradiation procedure. A picture of the setup can be seen below. For further
information on the setup, the irradiation procedure & characteristics or addiational material please visit the `homepage <https://www.zyklotron.hiskp.uni-bonn.de/zyklo/experiments_cyclotron_EN.html#one/>`_

.. image:: https://www.zyklotron.hiskp.uni-bonn.de/zyklo/images/hsr_exp_1_low.JPG
   :width: 800
   :align: center

Publications
============

Publications related to the proton irradiation site can be found below. If you are publishing results obtained by performing
irradiations or test beams at the proton irradiation site at Bonn university, please cite a suitable publication.

* 2022

    #. `D. Sauerland, R. Beck, J. Dingfelder, P.D. Eversheim, and P. Wolf, “Proton Irradiation Site for Si-Detectors at the Bonn Isochronous Cyclotron”, in Proc. IPAC'22, Bangkok, Thailand, Jun. 2022, pp. 130-132. doi:10.18429/JACoW-IPAC2022-MOPOST030 <https://ipac2022.vrws.de/papers/mopost030.pdf>`_


.. |test-status| image:: https://github.com/Silab-Bonn/irrad_control/actions/workflows/main.yml/badge.svg?branch=development
    :target: https://github.com/SiLab-Bonn/irrad_control/actions
    :alt: Build status
