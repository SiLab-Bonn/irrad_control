import logging
import pyqtgraph as pg
import numpy as np
from matplotlib import cm as mcmaps, colors as mcolors
from PyQt5 import QtWidgets, QtCore, QtGui
from collections import OrderedDict
from irrad_control.gui.widgets.util_widgets import GridContainer

# Matplotlib default colors
_MPL_COLORS = [tuple(round(255 * v) for v in rgb) for rgb in [mcolors.to_rgb(def_col) for def_col in mcolors.TABLEAU_COLORS]]

_BOLD_FONT = QtGui.QFont()
_BOLD_FONT.setBold(True)


class PlotWindow(QtWidgets.QMainWindow):
    """Window which only shows a PlotWidget as its central widget."""
        
    # PyQt signal which is emitted when the window closes
    closeWin = QtCore.pyqtSignal()

    def __init__(self, plot, parent=None):
        super(PlotWindow, self).__init__(parent)
        
        # PlotWidget to display in window
        self.pw = plot
        
        # Window appearance settings
        self.setWindowTitle(type(plot).__name__)
        self.screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setMinimumSize(0.75 * self.screen.width(), 0.75 * self.screen.height())
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        
        # Set plot as central widget
        self.setCentralWidget(self.pw)

    def closeEvent(self, _):
        self.closeWin.emit()
        self.close()


class PlotWrapperWidget(QtWidgets.QWidget):
    """Widget that wraps PlotWidgets and implements some additional features which allow to control the PlotWidgets content.
    Also adds button to show the respective PlotWidget in a QMainWindow"""

    def __init__(self, plot=None, parent=None):
        super(PlotWrapperWidget, self).__init__(parent=parent)

        # PlotWidget to display; set size policy 
        self.pw = plot
        self.pw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.external_win = None

        # Main layout and sub layout for e.g. checkboxes which allow to show/hide curves in PlotWidget etc.
        self.setLayout(QtWidgets.QVBoxLayout())
        self.plot_options = GridContainer(name='Plot options')
        
        # Setup widget if class instance was initialized with plot
        if self.pw is not None:
            self._setup_widget()

    def _setup_widget(self):
        """Setup of the additional widgets to control the appearance and content of the PlotWidget"""

        _sub_layout_1 = QtWidgets.QHBoxLayout()
        _sub_layout_1.setSpacing(self.plot_options.grid.verticalSpacing())
        _sub_layout_2 = QtWidgets.QHBoxLayout()
        _sub_layout_2.setSpacing(self.plot_options.grid.verticalSpacing())

        # Create checkboxes in order to show/hide curves in plots
        if hasattr(self.pw, 'show_data') and hasattr(self.pw, 'curves'):
            _sub_layout_2.addWidget(QtWidgets.QLabel('Toggle curve{}:'.format('s' if len(self.pw.curves) > 1 else '')))
            all_checkbox = QtWidgets.QCheckBox('All')
            all_checkbox.setFont(_BOLD_FONT)
            all_checkbox.setChecked(True)
            _sub_layout_2.addWidget(all_checkbox)
            for curve in self.pw.curves:
                checkbox = QtWidgets.QCheckBox(curve)
                checkbox.setChecked(True)
                all_checkbox.stateChanged.connect(lambda _, cbx=checkbox: cbx.setChecked(all_checkbox.isChecked()))
                checkbox.stateChanged.connect(lambda v, n=checkbox.text(): self.pw.show_data(n, bool(v)))
                _sub_layout_2.addWidget(checkbox)

        _sub_layout_1.addWidget(QtWidgets.QLabel('Features:'))
        _sub_layout_1.addStretch()

        # Add possibility to en/disable showing curve statistics
        if hasattr(self.pw, 'enable_stats'):
            stats_checkbox = QtWidgets.QCheckBox('Enable statistics')
            stats_checkbox.setChecked(self.pw._show_stats)
            stats_checkbox.stateChanged.connect(lambda state: self.pw.enable_stats(bool(state)))
            stats_checkbox.setToolTip("Show curve statistics while hovering / clicking curve(s)")
            _sub_layout_1.addWidget(stats_checkbox)

        # Whenever x axis is time add spinbox to change time period for which data is shown
        if hasattr(self.pw, 'update_period'):

            # Add horizontal helper line if we're looking at scrolling data plot
            unit = self.pw.plt.getAxis('left').labelUnits or '[?]'
            label = self.pw.plt.getAxis('left').labelText or 'Value'
            self.helper_line = pg.InfiniteLine(angle=0, label=label + ': {value:.2E} ' + unit)
            self.helper_line.setMovable(True)
            self.helper_line.setPen(color='w', style=pg.QtCore.Qt.DashLine, width=2)
            if hasattr(self.pw, 'unitChanged'):
                self.pw.unitChanged.connect(lambda u: setattr(self.helper_line.label, 'format', self.pw.plt.getAxis('left').labelText + ': {value:.2E} ' + u))
                self.pw.unitChanged.connect(self.helper_line.label.valueChanged)
            hl_checkbox = QtWidgets.QCheckBox('Show helper line')
            hl_checkbox.stateChanged.connect(
                lambda v: self.pw.plt.addItem(self.helper_line) if v else self.pw.plt.removeItem(self.helper_line))
            _sub_layout_1.addWidget(hl_checkbox)

            # Spinbox for period to be shown on x axis
            spinbox_period = QtWidgets.QSpinBox()
            spinbox_period.setRange(1, 3600)
            spinbox_period.setValue(self.pw._period)
            spinbox_period.setPrefix('Time period: ')
            spinbox_period.setSuffix(' s')
            spinbox_period.valueChanged.connect(lambda v: self.pw.update_period(v))
            _sub_layout_1.addWidget(spinbox_period)

        if hasattr(self.pw, 'update_refresh_rate'):

            # Spinbox for plot refresh rate
            spinbox_refresh = QtWidgets.QSpinBox()
            spinbox_refresh.setRange(0, 60)
            spinbox_refresh.setValue(int(1000 / self.pw.refresh_timer.interval()))
            spinbox_refresh.setPrefix('Refresh rate: ')
            spinbox_refresh.setSuffix(' Hz')
            spinbox_refresh.valueChanged.connect(lambda v: self.pw.update_refresh_rate(v))
            _sub_layout_1.addWidget(spinbox_refresh)

        # Button to move self.pw to PlotWindow instance
        self.btn_open = QtWidgets.QPushButton()
        self.btn_open.setIcon(self.btn_open.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton))
        self.btn_open.setToolTip('Open plot in window')
        self.btn_open.setFixedSize(25, 25)
        self.btn_open.clicked.connect(self.move_to_win)
        self.btn_open.clicked.connect(lambda: self.layout().insertStretch(1))
        self.btn_open.clicked.connect(lambda: self.btn_open.setEnabled(False))
        self.btn_open.clicked.connect(lambda: self.btn_close.setEnabled(True))

        # Button to close self.pw to PlotWindow instance
        self.btn_close = QtWidgets.QPushButton()
        self.btn_close.setIcon(self.btn_open.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton))
        self.btn_close.setToolTip('Close plot in window')
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(lambda: self.btn_close.setEnabled(False))
        self.btn_close.clicked.connect(lambda: self.external_win.close())

        _sub_layout_1.addWidget(self.btn_open)
        _sub_layout_1.addWidget(self.btn_close)

        self.plot_options.add_layout(_sub_layout_1)
        self.plot_options.add_layout(_sub_layout_2)
        
        # Insert everything into main layout
        self.layout().insertWidget(0, self.plot_options)
        self.layout().insertWidget(1, self.pw)

    def set_plot(self, plot):
        """Set PlotWidget and set up widgets"""
        self.pw = plot
        self._setup_widget()

    def move_to_win(self):
        """Move PlotWidget to PlotWindow. When window is closed, transfer widget back to self"""
        self.external_win = PlotWindow(plot=self.pw, parent=self)
        self.external_win.closeWin.connect(lambda: self.layout().takeAt(1))
        self.external_win.closeWin.connect(lambda: self.layout().insertWidget(1, self.pw))
        self.external_win.closeWin.connect(lambda: self.btn_open.setEnabled(True))
        self.external_win.show()


class IrradPlotWidget(pg.PlotWidget):
    """Base class for plot widgets"""

    def __init__(self, refresh_rate=20, parent=None):
        super(IrradPlotWidget, self).__init__(parent)

        # Actual plotitem
        self.plt = self.getPlotItem()

        # Store curves to be displayed and active
        self.curves = None

        # Hold data
        self._data = OrderedDict()
        self._data_is_set = False

        # Timer for refreshing plots with a given time interval to avoid unnecessary updating / high load
        self.refresh_timer = QtCore.QTimer()

        # Connect timeout signal of refresh timer to refresh_plot method
        self.refresh_timer.timeout.connect(self.refresh_plot)

        # Start timer
        self.refresh_timer.start(int(1000 / refresh_rate))

        # Hold buttons which are inside the plot
        self._in_plot_btns = []

    def _setup_plot(self):
        raise NotImplementedError('Please implement a _setup_plot method')

    def set_data(self):
        raise NotImplementedError('Please implement a set_data method')

    def refresh_plot(self):
        raise NotImplementedError('Please implement a refresh_plot method')

    def update_refresh_rate(self, refresh_rate):
        """Update rate with which the plot is drawn"""
        if refresh_rate == 0:
            logging.warning("{} display stopped. Data is not being buffered while not being displayed.".format(type(self).__name__))
            self.refresh_timer.stop()  # Stops QTimer
        else:
            self.refresh_timer.start(int(1000 / refresh_rate))  # Restarts QTimer with new updated interval

    def add_plot_button(self, btn):
        """Adds an in-plot button to the plotitem"""

        if btn not in self._in_plot_btns:
            self._in_plot_btns.append(btn)

        self._update_button_pos()

    def _update_button_pos(self, btn_spacing=20, x_offset=70, y_offset=5):

        btn_pos_x = x_offset
        btn_pos_y = y_offset

        is_visible = [b.isVisible() for b in self._in_plot_btns]

        for i, _btn in enumerate(self._in_plot_btns):

            # The first button will always be set to upper left corner
            # Check if the previous button was visible; if not, place at current position
            if i != 0 and is_visible[i - 1]:
                btn_pos_x += self._in_plot_btns[i - 1].boundingRect().width() + btn_spacing

            # Place button
            _btn.setPos(btn_pos_x, btn_pos_y)

    def show_data(self, curve=None, show=True):
        """Show/hide the data of curve in PlotItem. If *curve* is None, all curves are shown/hidden."""

        if not self.curves:
            raise NotImplementedError("Please define the attribute dict 'curves' and fill it with curves")

        if curve is not None and curve not in self.curves:
            logging.error('{} data not in graph. Current graphs: {}'.format(curve, ','.join(self.curves.keys())))
            return

        _curves = [curve] if curve is not None else self.curves.keys()

        for _cu in _curves:
            if isinstance(self.curves[_cu], CrosshairItem):
                self.curves[_cu].add_to_plot() if show else self.curves[_cu].remove_from_plot()
                self.curves[_cu].add_to_legend() if show else self.curves[_cu].remove_from_legend()
            else:

                if not any(isinstance(self.curves[_cu], x) for x in (pg.InfiniteLine, pg.ImageItem)):
                    self.legend.addItem(self.curves[_cu], _cu) if show else self.legend.removeItem(_cu)

                self.plt.addItem(self.curves[_cu]) if show else self.plt.removeItem(self.curves[_cu])


class ScrollingIrradDataPlot(IrradPlotWidget):
    """PlotWidget which displays a set of irradiation data curves over time"""

    def __init__(self, channels, units=None, period=60, refresh_rate=20, colors=_MPL_COLORS, name=None, parent=None):
        super(ScrollingIrradDataPlot, self).__init__(refresh_rate=refresh_rate, parent=parent)

        self.channels = channels
        self.units = units
        self.name = name

        # Attributes for data visualization
        self._time = None  # array for timestamps
        self._data = None
        self._start = 0  # starting timestamp of each cycle
        self._timestamp = 0  # timestamp of each incoming data
        self._offset = 0  # offset for increasing cycle time
        self._idx = 0  # cycling index through time axis
        self._period = period  # amount of time for which to display data; default, displaying last 60 seconds of data
        self._filled = False  # bool to see whether the array has been filled
        self._drate = None  # data rate
        self._colors = colors  # Colors to plot curves in
        self._show_stats = True  # Show statistics of curves

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):
        """Setting up the plot. The Actual plot (self.plt) is the underlying PlotItem of the respective PlotWidget"""

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setLabel('left', text='Signal', units='V' if self.units is None else self.units['left'])

        # Title
        self.plt.setTitle('' if self.name is None else self.name)

        # Additional axis if specified
        if 'right' in self.units:
            self.plt.setLabel('right', text='Signal', units=self.units['right'])

        # X-axis is time
        self.plt.setLabel('bottom', text='Time', units='s')
        self.plt.showGrid(x=True, y=True, alpha=0.66)
        self.plt.setLimits(xMax=0)

        # Make OrderedDict of curves and dict to hold active value indicating whether the user interacts with the curve
        self.curves = OrderedDict([(ch, pg.PlotCurveItem(pen=self._colors[i % len(self._colors)])) for i, ch in enumerate(self.channels)])
        self.active_curves = None  # Store channel which is currently active (e.g. statistics are shown)

        # TextItem for showing statistic of curves; set invisible first, only show on user request
        self.stat_text = pg.TextItem(text='', border=pg.mkPen(color='w', style=pg.QtCore.Qt.SolidLine))
        self.stat_text.setParentItem(self.plt)
        self.enable_stats()
        self.stat_text.setVisible(False)
        self._static_stat_text = False

        # Make legend entries for curves
        self.legend = pg.LegendItem(offset=(80, -50))
        self.legend.setParentItem(self.plt)

        # Show data and legend
        for ch in self.channels:
            self.show_data(ch)
            self.curves[ch].opts['mouseWidth'] = 20  # Needed for indication of active curves

    def enable_stats(self, enable=True):

        def _manage_signals(sig, slot, connect):

            try:
                sig.connect(slot) if connect else sig.disconnect(slot)
            except Exception:
                logging.error('Signal {} not {} slot {}'.format(repr(sig), '{}connected {}'.format(*('', 'to') if connect else ('dis', 'from')), repr(slot)))

        # Set flag
        self._show_stats = enable

        # Signals
        _manage_signals(sig=self.plt.scene().sigMouseMoved, slot=self._set_active_curves, connect=enable)
        _manage_signals(sig=self.plt.scene().sigMouseClicked, slot=self._set_active_curves, connect=enable)
        _manage_signals(sig=self.plt.scene().sigMouseClicked, slot=self._toggle_static_stat_text, connect=enable)

        # Stat text visibility
        self.stat_text.setVisible(enable)

    def _toggle_static_stat_text(self, click):
        self._static_stat_text = not self._static_stat_text if self.active_curves else False
        self._set_active_curves(click)

    def _set_active_curves(self, event):
        """Method updating which curves are active; active curves statistics are shown on plot"""

        if self._static_stat_text:
            return

        # Check whether it was a click or move
        click = hasattr(event, 'button')

        # Get mouse coordinates in the coordinate system of the plot
        mouse_coordinates = self.plt.vb.mapSceneToView(event if not click else event.scenePos())

        # Update current active curves
        self.active_curves = [ch for ch in self.channels if self.curves[ch].mouseShape().contains(mouse_coordinates)]

        # We have active curves
        if self.active_curves:
            # self.plt.width() - 1.1 * self.stat_text.boundingRect().width(), self.plt.height() * 0.01
            self.stat_text.setPos(event if not click else event.scenePos())
            self.stat_text.setVisible(True)
        else:
            self.stat_text.setVisible(False)

    def _set_stats(self):
        """Show curve statistics for active_curves which have been clicked or are hovered over"""

        if not self.active_curves:
            return

        n_actives = len(self.active_curves)

        # Update text for statistics widget
        current_stat_text = 'Curve stats of {} curve{}:\n'.format(n_actives, '' if n_actives == 1 else 's')

        # Loop over active curves and create current stats
        for curve in self.active_curves:

            # If data is not yet filled; mask all NaN values and invert bool mask
            mask = None if self._filled else ~np.isnan(self._data[curve])

            # Get stats
            if mask is None:
                mean, std, entries = self._data[curve].mean(), self._data[curve].std(), self._data[curve].shape[0]
            else:
                mean, std, entries = self._data[curve][mask].mean(), self._data[curve][mask].std(), self._data[curve][mask].shape[0]

            current_stat_text += '  '
            current_stat_text += curve + u': ({:.2E} \u00B1 {:.2E}) {} (#{})'.format(mean, std, self.plt.getAxis('left').labelUnits, entries)
            current_stat_text += '\n' if curve != self.active_curves[-1] else ''

        # Set color and text
        current_stat_color = (100, 100, 100) if n_actives != 1 else self.curves[self.active_curves[0]].opts['pen'].color()
        self.stat_text.fill = pg.mkBrush(color=current_stat_color, style=pg.QtCore.Qt.SolidPattern)
        self.stat_text.setText(current_stat_text)

    def set_data(self, data):
        """Set the data of the plot. Input data is data plus meta data"""

        # Meta data and data
        _meta, _data = data['meta'], data['data']

        # Store timestamp of current data
        self._timestamp = _meta['timestamp']

        # Set data rate if available
        if 'data_rate' in _meta:
            self._drate = _meta['data_rate']

        # Get data rate from data in order to set time axis
        if self._time is None:
            if 'data_rate' in _meta:
                self._drate = _meta['data_rate']
                shape = int(round(self._drate) * self._period + 1)
                self._time = np.full(shape=shape, fill_value=np.nan)  # np.zeros(shape=shape)
                self._data = OrderedDict([(ch, np.full(shape=shape, fill_value=np.nan)) for i, ch in enumerate(self.channels)])
                self._data_is_set = True

        # Fill data
        else:

            # If we made one cycle, start again from the beginning
            if self._idx == self._time.shape[0]:
                self._idx = 0
                self._filled = True

            # If we start a new cycle, set new start timestamp and offset
            if self._idx == 0:
                self._start = self._timestamp
                self._offset = 0

            # Set time axis
            self._time[self._idx] = self._start - self._timestamp + self._offset

            # Increment index
            self._idx += 1

            # Set data in curves
            for ch in _data:
                # Shift data to the right and set 0th element
                self._data[ch][1:] = self._data[ch][:-1]
                self._data[ch][0] = _data[ch]

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        if self._data_is_set:
            for curve in self.curves:

                # Update data of curves
                if not self._filled:
                    mask = ~np.isnan(self._data[curve])  # Mask all NaN values and invert bool mask
                    self.curves[curve].setData(self._time[mask], self._data[curve][mask])
                else:
                    self.curves[curve].setData(self._time, self._data[curve])

            # Only calculate statistics if we look at them
            if self._show_stats:
                self._set_stats()

    def update_axis_scale(self, scale, axis='left'):
        """Update the scale of current axis"""
        self.plt.getAxis(axis).setScale(scale=scale)

    def update_period(self, period):
        """Update the period of time for which the data is displayed in seconds"""

        # Update attribute
        self._period = period

        # Create new data and time
        shape = int(round(self._drate) * self._period + 1)
        new_data = OrderedDict([(ch, np.full(shape=shape, fill_value=np.nan)) for i, ch in enumerate(self.channels)])
        new_time = np.full(shape=shape, fill_value=np.nan)

        # Check whether new time and data hold more or less indices
        decreased = self._time.shape[0] >= shape

        if decreased:
            # Cut time axis
            new_time = self._time[:shape]

            # If filled before, go to 0, else go to 0 if current index is bigger than new shape
            if self._filled:
                self._idx = 0
            else:
                self._idx = 0 if self._idx >= shape else self._idx

            # Set wheter the array is now filled
            self._filled = True if self._idx == 0 else False

        else:
            # Extend time axis
            new_time[:self._time.shape[0]] = self._time

            # If array was filled before, go to last time, set it as offset and start from last timestamp
            if self._filled:
                self._idx = self._time.shape[0]
                self._start = self._timestamp
                self._offset = self._time[-1]

            self._filled = False

        # Set new time and data
        for ch in self.channels:
            if decreased:
                new_data[ch] = self._data[ch][:shape]
            else:
                new_data[ch][:self._data[ch].shape[0]] = self._data[ch]

        # Update
        self._time = new_time
        self._data = new_data


class RawDataPlot(ScrollingIrradDataPlot):
    """Plot for displaying the raw data of all channels of the respective ADC over time.
        Data is displayed in rolling manner over period seconds. The plot  unit can be switched between Volt and Ampere"""

    unitChanged = QtCore.pyqtSignal(str)

    def __init__(self, daq_setup, daq_device=None, parent=None):

        # Init class attributes
        self.daq_setup = daq_setup

        self.use_unit = 'V'

        # Call __init__ of ScrollingIrradDataPlot
        super(RawDataPlot, self).__init__(channels=daq_setup['devices']['adc']['channels'], units={'left': self.use_unit},
                                          name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                          parent=parent)

        # Make in-plot button to switch between units
        unit_btn = PlotPushButton(plotitem=self.plt, text='Switch unit ({})'.format('A'))
        unit_btn.clicked.connect(self.change_unit)

        # Connect to signal
        for con in [lambda u: self.plt.getAxis('left').setLabel(text='Signal', units=u),
                    lambda u: unit_btn.setText('Switch unit ({})'.format('A' if u == 'V' else 'V')),
                    lambda u: setattr(self, '_data', self.convert_to_unit(self._data, u))]:  # convert between units
            self.unitChanged.connect(con)

        # Add
        self.add_plot_button(unit_btn)

    def change_unit(self):
        self.use_unit = 'V' if self.use_unit == 'A' else 'A'
        self.unitChanged.emit(self.use_unit)

    def convert_to_unit(self, data, unit):
        """Method to convert raw data between Volt and Ampere"""

        # Check whether data is not None
        if not data:
            logging.info('No data to convert')
            return

        res = OrderedDict()

        # Loop over data and overwrite
        for ch in data:
            _idx = self.channels.index(ch)
            # Get data, scale and type of channel
            val, scale, _type = data[ch], self.daq_setup['devices']['adc']['ro_scales'][_idx], self.daq_setup['devices']['adc']['types'][_idx]
            # Adjust scale in case we're looking at SEM's sum signal; in this case current is multiplied by factor of 4
            scale *= 1 if _type != 'sem_sum' else 4

            res[ch] = val / 5.0 * scale * 1e-9 if unit == 'A' else val * 5.0 / 1e-9 / scale

        return res

    def set_data(self, data):
        """Overwrite set_data method in order to show raw data in Ampere and Volt"""

        # Convert voltages to currents and overwrite
        if self.use_unit == 'A':
            data['data'] = self.convert_to_unit(data['data'], self.use_unit)

        super(RawDataPlot, self).set_data(data)


class PlotPushButton(pg.TextItem):
    """Implements a in-plot push button for a PlotItem"""

    clicked = QtCore.pyqtSignal()

    def __init__(self, plotitem, **kwargs):

        if 'border' not in kwargs:
            kwargs['border'] = pg.mkPen(color='w', style=pg.QtCore.Qt.SolidLine)

        super(PlotPushButton, self).__init__(**kwargs)

        self.setParentItem(plotitem)
        self.setOpacity(0.7)
        self.btn_area = QtCore.QRectF(self.mapToParent(self.boundingRect().topLeft()), self.mapToParent(self.boundingRect().bottomRight()))

        # Connect to relevant signals
        plotitem.scene().sigMouseMoved.connect(self._check_hover)
        plotitem.scene().sigMouseClicked.connect(self._check_click)

    def setPos(self, *args, **kwargs):
        super(PlotPushButton, self).setPos(*args, **kwargs)
        self.btn_area = QtCore.QRectF(self.mapToParent(self.boundingRect().topLeft()), self.mapToParent(self.boundingRect().bottomRight()))

    def setFill(self, *args, **kwargs):
        self.fill = pg.mkBrush(*args, **kwargs)

    def _check_hover(self, evt):
        if self.btn_area.contains(evt):
            self.setOpacity(1.0)
        else:
            self.setOpacity(0.7)

    def _check_click(self, b):
        if self.btn_area.contains(b.scenePos()):
            self.clicked.emit()


class BeamCurrentPlot(ScrollingIrradDataPlot):
    """Plot for displaying the proton beam current over time. Data is displayed in rolling manner over period seconds"""

    def __init__(self, beam_current_setup=None, daq_device=None, parent=None):

        # Init class attributes
        self.beam_current_setup = beam_current_setup

        # Call __init__ of ScrollingIrradDataPlot
        super(BeamCurrentPlot, self).__init__(channels=['analog', 'digital'], units={'left': 'A', 'right': 'A'},
                                              name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                              parent=parent)

        self.plt.setLabel('left', text='Beam current', units='A')
        self.plt.hideAxis('left')
        self.plt.showAxis('right')
        self.plt.setLabel('right', text='Beam current', units='A')


class TemperatureDataPlot(ScrollingIrradDataPlot):

    def __init__(self, temp_setup, daq_device=None, parent=None):

        self.temp_setup = temp_setup

        super(TemperatureDataPlot, self).__init__(channels=temp_setup['devices']['temp'].values(), units={'right': 'C', 'left': 'C'},
                                                  name=type(self).__name__ + ('' if daq_device is None else ' ' + daq_device),
                                                  parent=parent)

        self.plt.setLabel('left', text='Temperature', units='C')
        self.plt.hideAxis('left')
        self.plt.showAxis('right')
        self.plt.setLabel('right', text='Temperature', units='C')


class CrosshairItem:
    """This class implements three pyqtgraph items in order to display a reticle with a circle in its intersection."""

    def __init__(self, color, name, intersect_symbol=None, horizontal=True, vertical=True):

        if not horizontal and not vertical:
            raise ValueError('At least one of horizontal or vertical beam position must be true!')

        # Whether to show horizontal and vertical lines
        self.horizontal = horizontal
        self.vertical = vertical

        # Init items needed
        self.h_shift_line = pg.InfiniteLine(angle=90)
        self.v_shift_line = pg.InfiniteLine(angle=0)
        self.intersect = pg.ScatterPlotItem()

        # Drawing style
        self.h_shift_line.setPen(color=color, style=pg.QtCore.Qt.SolidLine, width=2)
        self.v_shift_line.setPen(color=color, style=pg.QtCore.Qt.SolidLine, width=2)
        self.intersect.setPen(color=color, style=pg.QtCore.Qt.SolidLine)
        self.intersect.setBrush(color=color)
        self.intersect.setSymbol('o' if intersect_symbol is None else intersect_symbol)
        self.intersect.setSize(10)

        # Items
        self.items = []

        # Add the respective lines
        if self.horizontal and self.vertical:
            self.items = [self.intersect, self.h_shift_line, self.v_shift_line]
        elif self.horizontal:
            self.items.append(self.h_shift_line)
        else:
            self.items.append(self.v_shift_line)

        self.legend = None
        self.plotitem = None
        self.name = name

    def set_position(self, x=None, y=None):

        if x is None and y is None:
            raise ValueError('Either x or y position have to be given!')

        if self.horizontal:
            _x = x if x is not None else self.h_shift_line.value()

        if self.vertical:
            _y = y if y is not None else self.v_shift_line.value()

        if self.horizontal and self.vertical:
            self.h_shift_line.setValue(_x)
            self.v_shift_line.setValue(_y)
            self.intersect.setData([_x], [_y])
        elif self.horizontal:
            self.h_shift_line.setValue(_x)
        else:
            self.v_shift_line.setValue(_y)

    def set_plotitem(self, plotitem):
        self.plotitem = plotitem

    def set_legend(self, legend):
        self.legend = legend

    def add_to_plot(self, plotitem=None):

        if plotitem is None and self.plotitem is None:
            raise ValueError('PlotItem item needed!')

        for item in self.items:
            if plotitem is None:
                self.plotitem.addItem(item)
            else:
                plotitem.addItem(item)

    def add_to_legend(self, label=None, legend=None):

        if legend is None and self.legend is None:
            raise ValueError('LegendItem needed!')

        _lbl = label if label is not None else self.name

        if legend is None:
            self.legend.addItem(self.intersect, _lbl)
        else:
            legend.addItem(self.intersect, _lbl)

    def remove_from_plot(self, plotitem=None):

        if plotitem is None and self.plotitem is None:
            raise ValueError('PlotItem item needed!')

        for item in self.items:
            if plotitem is None:
                self.plotitem.removeItem(item)
            else:
                plotitem.removeItem(item)

    def remove_from_legend(self, label=None, legend=None):

        if legend is None and self.legend is None:
            raise ValueError('LegendItem needed!')

        _lbl = label if label is not None else self.name

        if legend is None:
            self.legend.removeItem(_lbl)
        else:
            legend.removeItem(_lbl)


class BeamPositionPlot(IrradPlotWidget):
    """
    Plot for displaying the beam position. The position is displayed from analog and digital data if available.
    """

    def __init__(self, daq_setup, position_range=None, daq_device=None, add_hist=True, parent=None):
        super(BeamPositionPlot, self).__init__(parent=parent)

        # Init class attributes
        self.daq_setup = daq_setup
        self.ro_types = daq_setup['devices']['adc']['types']
        self.daq_device = daq_device
        self._plt_range = position_range if position_range else [-110, 110] * 2
        self._add_hist = add_hist

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(type(self).__name__ if self.daq_device is None else type(self).__name__ + ' ' + self.daq_device)
        self.plt.setLabel('left', text='Vertical displacement', units='%')
        self.plt.setLabel('bottom', text='Horizontal displacement', units='%')
        self.plt.showGrid(x=True, y=True, alpha=0.99)
        self.plt.setRange(xRange=self._plt_range[:2], yRange=self._plt_range[2:])
        self.plt.setLimits(**dict([(k, self._plt_range[i]) for i, k in enumerate(('xMin', 'xMax', 'yMin', 'yMax'))]))
        self.plt.hideButtons()
        v_line = self.plt.addLine(x=0, pen={'color': 'w', 'style': pg.QtCore.Qt.DashLine})
        h_line = self.plt.addLine(y=0., pen={'color': 'w', 'style': pg.QtCore.Qt.DashLine})
        _ = pg.InfLineLabel(line=h_line, text='Left', position=0.05, movable=False)
        _ = pg.InfLineLabel(line=h_line, text='Right', position=0.95, movable=False)
        _ = pg.InfLineLabel(line=v_line, text='Up', position=0.95, movable=False)
        _ = pg.InfLineLabel(line=v_line, text='Down', position=0.05, movable=False)
        self.legend = pg.LegendItem(offset=(80, -50))
        self.legend.setParentItem(self.plt)

        self.curves = OrderedDict()

        if any(x in self.ro_types for x in ('sem_h_shift', 'sem_v_shift')):
            sig = 'analog'
            self.curves[sig] = CrosshairItem(color=_MPL_COLORS[0], name=sig,
                                             horizontal='sem_h_shift' in self.ro_types,
                                             vertical='sem_v_shift' in self.ro_types)

            # Add 2D histogram
            if self._add_hist:
                self.add_2d_hist(curve=sig, autoDownsample=True, opacity=0.66, cmap='hot')

        if any(all(x in self.ro_types for x in y) for y in [('sem_left', 'sem_right'), ('sem_up', 'sem_down')]):
            sig = 'digital'
            self.curves[sig] = CrosshairItem(color=_MPL_COLORS[1], name=sig,
                                             horizontal='sem_left' in self.ro_types and 'sem_right' in self.ro_types,
                                             vertical='sem_up' in self.ro_types and 'sem_down' in self.ro_types)
            # Add 2D histogram
            if self._add_hist:
                self.add_2d_hist(curve=sig, autoDownsample=True, opacity=0.66, cmap='hot')

        # Show data and legend
        if self.curves:
            for curve in self.curves:
                if isinstance(self.curves[curve], CrosshairItem):
                    self.curves[curve].set_legend(self.legend)
                    self.curves[curve].set_plotitem(self.plt)
                self.show_data(curve)

    def add_2d_hist(self, curve, cmap='hot', bins=(51, 51), **kwargs):

        if curve not in self.curves:
            logging.error("Can only add histogram to existing curve")
            return

        if len(bins) != 2:
            raise ValueError("Bins must be iterable of integers of len 2")

        hist_name = curve + '_hist'

        if 'lut' not in kwargs:
            # Create colormap and init
            colormap = mcmaps.get_cmap(cmap)
            colormap._init()

            # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
            lut = (colormap._lut * 255).view(np.ndarray)
            # Update kw
            kwargs['lut'] = lut

        # Add and show
        self.curves[hist_name] = pg.ImageItem(**kwargs)
        self.show_data(hist_name)

        get_scale = lambda plt_range, n_bins: float(abs(plt_range[0] - plt_range[1])) / n_bins

        # Manage position
        self.curves[hist_name].translate(self._plt_range[0], self._plt_range[2])
        self.curves[hist_name].scale(get_scale(self._plt_range[:2], bins[0]), get_scale(self._plt_range[2:], bins[1]))
        self.curves[hist_name].setZValue(-10)

        # Add hist data
        self._data[hist_name] = {}
        self._data[hist_name]['hist'] = np.zeros(shape=bins)
        self._data[hist_name]['edges'] = (np.linspace(self._plt_range[0], self._plt_range[1], bins[0]),
                                          np.linspace(self._plt_range[2], self._plt_range[3], bins[1]))

    def set_data(self, data):

        # Meta data and data
        meta, pos_data = data['meta'], data['data']['position']

        for sig in pos_data:
            if sig not in self.curves:
                continue
            h_shift = None if 'h' not in pos_data[sig] else pos_data[sig]['h']
            v_shift = None if 'v' not in pos_data[sig] else pos_data[sig]['v']

            # Update data
            self._data[sig] = (h_shift, v_shift)

            if sig + '_hist' in self.curves and all(x is not None for x in self._data[sig]):
                # Get histogram indices and increment
                idx_x, idx_y = (np.searchsorted(self._data[sig + '_hist']['edges'][i], self._data[sig][i]) for i in range(len(self._data[sig])))
                self._data[sig + '_hist']['hist'][idx_x, idx_y] += 1

        self._data_is_set = True

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        if self._data_is_set:
            for sig in self.curves:
                if sig not in self._data:
                    continue
                if isinstance(self.curves[sig], CrosshairItem):
                    self.curves[sig].set_position(*self._data[sig])
                else:
                    self.curves[sig].setImage(self._data[sig]['hist'])


class FluenceHist(IrradPlotWidget):
    """
        Plot for displaying the beam position. The position is displayed from analog and digital data if available.
        """

    def __init__(self, irrad_setup, refresh_rate=5, daq_device=None, parent=None):
        super(FluenceHist, self).__init__(refresh_rate=refresh_rate, parent=parent)

        # Init class attributes
        self.irrad_setup = irrad_setup
        self.daq_device = daq_device

        self._data['hist_rows'] = np.arange(self.irrad_setup['n_rows'] + 1)

        # Setup the main plot
        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(type(self).__name__ if self.daq_device is None else type(self).__name__ + ' ' + self.daq_device)
        self.plt.setLabel('left', text='Proton fluence', units='cm^-2')
        self.plt.setLabel('right', text='Neutron fluence', units='cm^-2')
        self.plt.setLabel('bottom', text='Scan row')
        self.plt.getAxis('right').setScale(self.irrad_setup['kappa'])
        self.plt.getAxis('left').enableAutoSIPrefix(False)
        self.plt.getAxis('right').enableAutoSIPrefix(False)
        self.plt.setLimits(xMin=0, xMax=self.irrad_setup['n_rows'], yMin=0)
        self.legend = pg.LegendItem(offset=(80, 80))
        self.legend.setParentItem(self.plt)

        # Histogram of fluence per row
        hist_curve = pg.PlotCurveItem()
        hist_curve.setFillLevel(0.33)
        hist_curve.setBrush(pg.mkBrush(color=_MPL_COLORS[0]))

        # Points at respective row positions
        hist_points = pg.ScatterPlotItem()
        hist_points.setPen(color=_MPL_COLORS[2], style=pg.QtCore.Qt.SolidLine)
        hist_points.setBrush(color=_MPL_COLORS[2])
        hist_points.setSymbol('o')
        hist_points.setSize(10)

        # Errorbars for points; needs to initialized with x, y args, otherwise cnnot be added to PlotItem
        hist_errors = pg.ErrorBarItem(x=np.arange(1), y=np.arange(1), beam=0.25)

        # Horizontal line indication the mean fluence over all rows
        mean_curve = pg.InfiniteLine(angle=0)
        mean_curve.setPen(color=_MPL_COLORS[1], width=2)
        self.p_label = pg.InfLineLabel(mean_curve, position=0.2)
        self.n_label = pg.InfLineLabel(mean_curve, position=0.8)

        self.curves = OrderedDict([('hist', hist_curve), ('hist_points', hist_points),
                                   ('hist_errors', hist_errors), ('mean', mean_curve)])

        # Show data and legend
        for curve in self.curves:
            self.show_data(curve)

    def set_data(self, data):

        # Meta data and data
        _meta, _data = data['meta'], data['data']

        # Set data
        self._data['hist'] = data['data']['hist']
        self._data['hist_err'] = data['data']['hist_err']

        # Get stats
        self._data['hist_mean'], self._data['hist_std'] = (f(self._data['hist']) for f in (np.mean, np.std))

        self._data_is_set = True

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""
        if self._data_is_set:
            for curve in self.curves:
                if curve == 'hist':
                    self.curves[curve].setData(x=self._data['hist_rows'], y=self._data['hist'], stepMode=True)
                    self.curves['mean'].setValue(self._data['hist_mean'])
                    self.p_label.setFormat('Mean: ({:.2E} +- {:.2E}) protons / cm^2'.format(self._data['hist_mean'], self._data['hist_std']))
                    self.n_label.setFormat('Mean: ({:.2E} +- {:.2E}) neq / cm^2'.format(*[x * self.irrad_setup['kappa'] for x in (self._data['hist_mean'],
                                                                                                                                  self._data['hist_std'])]))

                elif curve == 'hist_points':
                    self.curves[curve].setData(x=self._data['hist_rows'][:-1] + 0.5, y=self._data['hist'])
                elif curve == 'hist_errors':
                    self.curves[curve].setData(x=self._data['hist_rows'][:-1] + 0.5, y=self._data['hist'], height=np.array(self._data['hist_err']), pen=_MPL_COLORS[2])


class FractionHist(IrradPlotWidget):
    """This implements a histogram of the fraction of one signal to another"""

    def __init__(self, rel_sig, norm_sig, bins=100, colors=_MPL_COLORS, refresh_rate=10, parent=None):
        super(FractionHist, self).__init__(refresh_rate=refresh_rate, parent=parent)

        # Signal names; relative signal versus the signal it's normalized to
        self.rel_sig = rel_sig
        self.norm_sig = norm_sig

        # Get colors
        self.colors = colors

        # Hold data
        self._data['hist'], self._data['hist_edges'] = np.zeros(shape=bins), np.linspace(0, 100, bins + 1)

        self._setup_plot()

    def _setup_plot(self):

        # Get plot item and setup
        self.plt.setDownsampling(auto=True)
        self.plt.setTitle(type(self).__name__ + ' ' + self.rel_sig)
        self.plt.setLabel('left', text='#')
        self.plt.setLabel('bottom', text='Fraction {} / {}'.format(self.rel_sig, self.norm_sig))
        self.plt.getAxis('left').enableAutoSIPrefix(False)
        self.plt.showGrid(x=True, y=True)
        self.plt.setLimits(xMin=0, xMax=self._data['hist_edges'].shape[0], yMin=0)
        self.legend = pg.LegendItem(offset=(80, 80))
        self.legend.setParentItem(self.plt)

        # Histogram of fraction
        hist_curve = pg.PlotCurveItem(name='{} / {} histogram'.format(self.rel_sig, self.norm_sig))
        hist_curve.setFillLevel(0.33)
        hist_curve.setBrush(pg.mkBrush(color=self.colors[0]))

        # Init items needed
        current_fraction_curve = CrosshairItem(color=self.colors[1], name='Current bin')
        current_fraction_curve.v_shift_line.setValue(5)  # Make crosshair point visible above 0
        current_fraction_curve.v_shift_line.setVisible(False)  # We need x and y for the dot in the middle but we don't want horizontal line to be visible
        current_fraction_curve.set_legend(self.legend)
        current_fraction_curve.set_plotitem(self.plt)

        # Make curves
        self.curves = OrderedDict([('hist', hist_curve), ('current_frac', current_fraction_curve)])

        # Show data and legend
        for curve in self.curves:
            self.show_data(curve)

    def set_data(self, data):

        # Meta data and data
        _meta, _data = data['meta'], data['data']

        # Store currrent fraction
        self._data['fraction'] = _data

        # Histogram fraction
        self._data['hist_idx'] = np.searchsorted(self._data['hist_edges'], _data)
        self._data['hist'][self._data['hist_idx']] += 1

        self._data_is_set = True

    def refresh_plot(self):
        """Refresh the plot. This method is supposed to be connected to the timeout-Signal of a QTimer"""

        # test if 'set_data' has been called
        if self._data_is_set:
            for curve in self.curves:

                if curve == 'hist':
                    self.curves[curve].setData(x=self._data['hist_edges'], y=self._data['hist'], stepMode=True)
                if curve == 'current_frac':
                    self.curves[curve].set_position(x=self._data['hist_idx'] + 0.5, y=self._data['hist'][self._data['hist_idx']])
