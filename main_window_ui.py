from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QAction


class MainWindowUIBuilder:
    """Builds the main window UI in code while keeping legacy widget names."""

    def setup(self, window: QtWidgets.QMainWindow):
        window.setObjectName("MainWindow")
        window.resize(1320, 860)

        self._create_actions(window)
        self._create_menu(window)

        window.centralwidget = QtWidgets.QWidget(window)
        window.centralwidget.setObjectName("centralwidget")
        window.setCentralWidget(window.centralwidget)

        root_layout = QtWidgets.QVBoxLayout(window.centralwidget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header(window))
        root_layout.addWidget(self._build_quick_actions(window))

        body_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        body_splitter.setChildrenCollapsible(False)
        root_layout.addWidget(body_splitter, 1)

        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        window.mainTabWidget = QtWidgets.QTabWidget()
        window.mainTabWidget.setObjectName("mainTabWidget")
        left_layout.addWidget(window.mainTabWidget, 1)

        window.mainTabWidget.addTab(self._build_stage_tab(window), "Stage")
        window.mainTabWidget.addTab(self._build_rf_tab(window), "RF")
        window.mainTabWidget.addTab(self._build_lia_tab(window), "LIA")
        window.mainTabWidget.addTab(self._build_scan_tab(window), "Scan")

        right_panel = self._build_status_panel(window)

        body_splitter.addWidget(left_panel)
        body_splitter.addWidget(right_panel)
        body_splitter.setStretchFactor(0, 4)
        body_splitter.setStretchFactor(1, 2)

        self._apply_main_styles(window)

    def _create_actions(self, window):
        window.actionChange_Max_Position_Values = QAction(window)
        window.actionChange_Max_Position_Values.setObjectName(
            "actionChange_Max_Position_Values"
        )
        window.actionChange_Max_Position_Values.setText("Change Max Position Values")

        window.actionDataViewer = QAction(window)
        window.actionDataViewer.setObjectName("actionDataViewer")
        window.actionDataViewer.setText("Data Viewer")

        window.actionDefaultParameters = QAction(window)
        window.actionDefaultParameters.setObjectName("actionDefaultParameters")
        window.actionDefaultParameters.setText("Set Default Parameters")

        window.actionLoadConfig = QAction(window)
        window.actionLoadConfig.setObjectName("actionLoadConfig")
        window.actionLoadConfig.setText("Load Config")

        window.actionSaveConfig = QAction(window)
        window.actionSaveConfig.setObjectName("actionSaveConfig")
        window.actionSaveConfig.setText("Save Config")

    def _create_menu(self, window):
        window.menubar = QtWidgets.QMenuBar(window)
        window.menubar.setObjectName("menubar")
        window.setMenuBar(window.menubar)

        window.menuConfig = QtWidgets.QMenu("Config", window.menubar)
        window.menuConfig.setObjectName("menuConfig")
        window.menuTools = QtWidgets.QMenu("Tools", window.menubar)
        window.menuTools.setObjectName("menuTools")

        window.menuConfig.addAction(window.actionLoadConfig)
        window.menuConfig.addAction(window.actionSaveConfig)
        window.menuConfig.addSeparator()
        window.menuConfig.addAction(window.actionDefaultParameters)

        window.menuTools.addAction(window.actionDataViewer)
        window.menuTools.addAction(window.actionChange_Max_Position_Values)

        window.menubar.addAction(window.menuConfig.menuAction())
        window.menubar.addAction(window.menuTools.menuAction())

    def _build_header(self, window):
        card = QtWidgets.QFrame()
        card.setObjectName("headerCard")
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        title_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("Scanning Magnetometer")
        title.setObjectName("titleLabel")
        subtitle = QtWidgets.QLabel("Code-built UI v1")
        subtitle.setObjectName("subtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        layout.addLayout(title_box)
        layout.addStretch(1)

        status_chip = QtWidgets.QLabel("Ready")
        status_chip.setObjectName("statusChip")
        layout.addWidget(status_chip)

        return card

    def _build_quick_actions(self, window):
        card = QtWidgets.QFrame()
        card.setObjectName("quickActionsCard")
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        window.startScanButton = QtWidgets.QPushButton("Start Scan")
        window.startScanButton.setObjectName("startScanButton")
        window.takeODMRButton = QtWidgets.QPushButton("Take ODMR")
        window.takeODMRButton.setObjectName("takeODMRButton")
        window.takeFFTButton = QtWidgets.QPushButton("Take FFT")
        window.takeFFTButton.setObjectName("takeFFTButton")
        window.openLIALiveTraceButton = QtWidgets.QPushButton("Open LIA Live Trace")
        window.openLIALiveTraceButton.setObjectName("openLIALiveTraceButton")
        window.vectorTestButton = QtWidgets.QPushButton("Vector Test")
        window.vectorTestButton.setObjectName("vectorTestButton")

        layout.addWidget(window.startScanButton)
        layout.addWidget(window.takeODMRButton)
        layout.addWidget(window.takeFFTButton)
        layout.addWidget(window.openLIALiveTraceButton)
        layout.addStretch(1)
        layout.addWidget(window.vectorTestButton)

        return card

    def _build_stage_tab(self, window):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        conn_group = QtWidgets.QGroupBox("Stage Connection")
        conn_form = QtWidgets.QFormLayout(conn_group)
        window.comPortBox = QtWidgets.QComboBox()
        window.comPortBox.setObjectName("comPortBox")
        window.connectStageButton = QtWidgets.QPushButton("Connect Stage")
        window.connectStageButton.setObjectName("connectStageButton")
        conn_form.addRow("COM Port", window.comPortBox)
        conn_form.addRow("", window.connectStageButton)
        conn_form.addRow(
            "Status", self._build_connection_indicator(window, "stage", "Disconnected")
        )

        move_group = QtWidgets.QGroupBox("Manual Stage Movement")
        move_grid = QtWidgets.QGridLayout(move_group)

        window.xPosSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.xPosSpinBox.setObjectName("xPosSpinBox")
        window.yPosSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.yPosSpinBox.setObjectName("yPosSpinBox")
        window.zPosSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.zPosSpinBox.setObjectName("zPosSpinBox")

        window.setPositionButton = QtWidgets.QPushButton("Set X/Y Position")
        window.setPositionButton.setObjectName("setPositionButton")
        window.setStageHeightButton = QtWidgets.QPushButton("Set Height (Z)")
        window.setStageHeightButton.setObjectName("setStageHeightButton")
        window.homeStageButton = QtWidgets.QPushButton("Home Stage")
        window.homeStageButton.setObjectName("homeStageButton")
        window.getStagePositionButton = QtWidgets.QPushButton("Get Position")
        window.getStagePositionButton.setObjectName("getStagePositionButton")

        move_grid.addWidget(QtWidgets.QLabel("X"), 0, 0)
        move_grid.addWidget(window.xPosSpinBox, 0, 1)
        move_grid.addWidget(QtWidgets.QLabel("Y"), 1, 0)
        move_grid.addWidget(window.yPosSpinBox, 1, 1)
        move_grid.addWidget(QtWidgets.QLabel("Z"), 2, 0)
        move_grid.addWidget(window.zPosSpinBox, 2, 1)
        move_grid.addWidget(window.setPositionButton, 0, 2)
        move_grid.addWidget(window.setStageHeightButton, 1, 2)
        move_grid.addWidget(window.homeStageButton, 2, 2)
        move_grid.addWidget(window.getStagePositionButton, 3, 2)

        layout.addWidget(conn_group)
        layout.addWidget(move_group)
        layout.addStretch(1)

        return tab

    def _build_rf_tab(self, window):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        conn_group = QtWidgets.QGroupBox("RF Source Connection")
        conn_form = QtWidgets.QFormLayout(conn_group)
        window.MWSourceIPAddressBox = QtWidgets.QLineEdit()
        window.MWSourceIPAddressBox.setObjectName("MWSourceIPAddressBox")
        window.connectMWSourceButton = QtWidgets.QPushButton("Connect RF Source")
        window.connectMWSourceButton.setObjectName("connectMWSourceButton")
        conn_form.addRow("IP Address", window.MWSourceIPAddressBox)
        conn_form.addRow("", window.connectMWSourceButton)
        conn_form.addRow(
            "Status", self._build_connection_indicator(window, "rf", "Disconnected")
        )

        rf_group = QtWidgets.QGroupBox("RF Parameters")
        rf_grid = QtWidgets.QGridLayout(rf_group)

        window.freqBox = self._make_spinbox(decimals=6, minimum=0.0, maximum=20.0)
        window.freqBox.setObjectName("freqBox")
        window.pwrBox = self._make_spinbox(decimals=3, minimum=-120.0, maximum=30.0)
        window.pwrBox.setObjectName("pwrBox")
        window.setFreqBtn = QtWidgets.QPushButton("Set Frequency")
        window.setFreqBtn.setObjectName("setFreqBtn")
        window.setPwrBtn = QtWidgets.QPushButton("Set Power")
        window.setPwrBtn.setObjectName("setPwrBtn")
        window.togglePwrChk = QtWidgets.QCheckBox("RF Power On")
        window.togglePwrChk.setObjectName("togglePwrChk")

        rf_grid.addWidget(QtWidgets.QLabel("Frequency (GHz)"), 0, 0)
        rf_grid.addWidget(window.freqBox, 0, 1)
        rf_grid.addWidget(window.setFreqBtn, 0, 2)
        rf_grid.addWidget(QtWidgets.QLabel("Power (dBm)"), 1, 0)
        rf_grid.addWidget(window.pwrBox, 1, 1)
        rf_grid.addWidget(window.setPwrBtn, 1, 2)
        rf_grid.addWidget(window.togglePwrChk, 2, 1)

        mod_group = QtWidgets.QGroupBox("Modulation")
        mod_grid = QtWidgets.QGridLayout(mod_group)

        window.modFreqSpinBox = self._make_spinbox(decimals=3, minimum=0.0, maximum=1e6)
        window.modFreqSpinBox.setObjectName("modFreqSpinBox")
        window.modAmpSpinBox = self._make_spinbox(decimals=3, minimum=0.0, maximum=1e6)
        window.modAmpSpinBox.setObjectName("modAmpSpinBox")
        window.applyModParamsButton = QtWidgets.QPushButton("Apply Mod Params")
        window.applyModParamsButton.setObjectName("applyModParamsButton")
        window.toggleModOnOff = QtWidgets.QCheckBox("Internal Mod On")
        window.toggleModOnOff.setObjectName("toggleModOnOff")
        window.toggleExtModOnOff = QtWidgets.QCheckBox("External Mod On")
        window.toggleExtModOnOff.setObjectName("toggleExtModOnOff")
        window.sineWaveRadio = QtWidgets.QRadioButton("Sine")
        window.sineWaveRadio.setObjectName("sineWaveRadio")
        window.squareWaveRadio = QtWidgets.QRadioButton("Square")
        window.squareWaveRadio.setObjectName("squareWaveRadio")

        wave_layout = QtWidgets.QHBoxLayout()
        wave_layout.addWidget(window.sineWaveRadio)
        wave_layout.addWidget(window.squareWaveRadio)
        wave_layout.addStretch(1)

        mod_grid.addWidget(QtWidgets.QLabel("Mod Frequency (kHz)"), 0, 0)
        mod_grid.addWidget(window.modFreqSpinBox, 0, 1)
        mod_grid.addWidget(QtWidgets.QLabel("Mod Amplitude (MHz)"), 1, 0)
        mod_grid.addWidget(window.modAmpSpinBox, 1, 1)
        mod_grid.addWidget(window.applyModParamsButton, 0, 2, 2, 1)
        mod_grid.addWidget(window.toggleModOnOff, 2, 0)
        mod_grid.addWidget(window.toggleExtModOnOff, 2, 1)
        mod_grid.addLayout(wave_layout, 3, 0, 1, 3)

        vector_group = QtWidgets.QGroupBox("Vector Tools")
        vector_layout = QtWidgets.QHBoxLayout(vector_group)
        window.setVectorMatrixButton = QtWidgets.QPushButton("Set Vector Matrix")
        window.setVectorMatrixButton.setObjectName("setVectorMatrixButton")
        vector_layout.addWidget(window.setVectorMatrixButton)
        vector_layout.addStretch(1)

        layout.addWidget(conn_group)
        layout.addWidget(rf_group)
        layout.addWidget(mod_group)
        layout.addWidget(vector_group)
        layout.addStretch(1)
        return tab

    def _build_lia_tab(self, window):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        conn_group = QtWidgets.QGroupBox("LIA Connection")
        conn_form = QtWidgets.QFormLayout(conn_group)
        window.LIANameBox = QtWidgets.QLineEdit()
        window.LIANameBox.setObjectName("LIANameBox")
        window.LIAIPBox = QtWidgets.QLineEdit()
        window.LIAIPBox.setObjectName("LIAIPBox")
        window.connectLIAButton = QtWidgets.QPushButton("Connect LIA")
        window.connectLIAButton.setObjectName("connectLIAButton")
        conn_form.addRow("Device ID", window.LIANameBox)
        conn_form.addRow("Device IP", window.LIAIPBox)
        conn_form.addRow("", window.connectLIAButton)
        conn_form.addRow(
            "Status", self._build_connection_indicator(window, "lia", "Disconnected")
        )

        runtime_group = QtWidgets.QGroupBox("Runtime Settings")
        runtime_grid = QtWidgets.QGridLayout(runtime_group)

        window.scalingFactorSpinBox = QtWidgets.QSpinBox()
        window.scalingFactorSpinBox.setObjectName("scalingFactorSpinBox")
        window.scalingFactorSpinBox.setRange(1, 100000)
        window.timeConstantSpinBox = QtWidgets.QSpinBox()
        window.timeConstantSpinBox.setObjectName("timeConstantSpinBox")
        window.timeConstantSpinBox.setRange(1, 10000000)

        window.rangeSelect = QtWidgets.QComboBox()
        window.rangeSelect.setObjectName("rangeSelect")
        window.rangeSelect.addItems(["0", "0.01", "0.03", "0.1", "0.3", "1", "3", "10"])

        window.harmonicOrderSelect = QtWidgets.QComboBox()
        window.harmonicOrderSelect.setObjectName("harmonicOrderSelect")
        window.harmonicOrderSelect.addItems([str(i) for i in range(1, 9)])

        window.acCoupleCheck = QtWidgets.QCheckBox("AC Coupling")
        window.acCoupleCheck.setObjectName("acCoupleCheck")
        window.fiftyOhmCheck = QtWidgets.QCheckBox("50 Ohm")
        window.fiftyOhmCheck.setObjectName("fiftyOhmCheck")

        runtime_grid.addWidget(QtWidgets.QLabel("Scaling"), 0, 0)
        runtime_grid.addWidget(window.scalingFactorSpinBox, 0, 1)
        runtime_grid.addWidget(QtWidgets.QLabel("Time Constant (us)"), 1, 0)
        runtime_grid.addWidget(window.timeConstantSpinBox, 1, 1)
        runtime_grid.addWidget(QtWidgets.QLabel("Input Range"), 2, 0)
        runtime_grid.addWidget(window.rangeSelect, 2, 1)
        runtime_grid.addWidget(QtWidgets.QLabel("Filter Order"), 3, 0)
        runtime_grid.addWidget(window.harmonicOrderSelect, 3, 1)
        runtime_grid.addWidget(window.acCoupleCheck, 4, 0)
        runtime_grid.addWidget(window.fiftyOhmCheck, 4, 1)

        acq_group = QtWidgets.QGroupBox("Acquisition")
        acq_grid = QtWidgets.QGridLayout(acq_group)

        window.odmrAqDurBox = QtWidgets.QSpinBox()
        window.odmrAqDurBox.setObjectName("odmrAqDurBox")
        window.odmrAqDurBox.setRange(1, 100000)

        window.odmrAqBurstDurBox = self._make_spinbox(decimals=6, minimum=0.000001, maximum=1000)
        window.odmrAqBurstDurBox.setObjectName("odmrAqBurstDurBox")

        window.odmrAqSampleRateBox = QtWidgets.QSpinBox()
        window.odmrAqSampleRateBox.setObjectName("odmrAqSampleRateBox")
        window.odmrAqSampleRateBox.setRange(1, 5000000)

        window.fftAverageSpinBox = QtWidgets.QSpinBox()
        window.fftAverageSpinBox.setObjectName("fftAverageSpinBox")
        window.fftAverageSpinBox.setRange(1, 100000)

        window.fftDurationSpinBox = QtWidgets.QSpinBox()
        window.fftDurationSpinBox.setObjectName("fftDurationSpinBox")
        window.fftDurationSpinBox.setRange(1, 100000)

        window.sampleRateSpinBox = QtWidgets.QSpinBox()
        window.sampleRateSpinBox.setObjectName("sampleRateSpinBox")
        window.sampleRateSpinBox.setRange(1, 5000000)

        acq_grid.addWidget(QtWidgets.QLabel("ODMR Duration (s)"), 0, 0)
        acq_grid.addWidget(window.odmrAqDurBox, 0, 1)
        acq_grid.addWidget(QtWidgets.QLabel("ODMR Burst Duration (s)"), 1, 0)
        acq_grid.addWidget(window.odmrAqBurstDurBox, 1, 1)
        acq_grid.addWidget(QtWidgets.QLabel("ODMR Sample Rate"), 2, 0)
        acq_grid.addWidget(window.odmrAqSampleRateBox, 2, 1)
        acq_grid.addWidget(QtWidgets.QLabel("FFT Averages"), 3, 0)
        acq_grid.addWidget(window.fftAverageSpinBox, 3, 1)
        acq_grid.addWidget(QtWidgets.QLabel("FFT Duration (s)"), 4, 0)
        acq_grid.addWidget(window.fftDurationSpinBox, 4, 1)
        acq_grid.addWidget(QtWidgets.QLabel("FFT Sample Rate"), 5, 0)
        acq_grid.addWidget(window.sampleRateSpinBox, 5, 1)

        layout.addWidget(conn_group)
        layout.addWidget(runtime_group)
        layout.addWidget(acq_group)
        layout.addStretch(1)

        return tab

    def _build_scan_tab(self, window):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        area_group = QtWidgets.QGroupBox("Scan Area")
        area_grid = QtWidgets.QGridLayout(area_group)

        window.xStartSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.xStartSpinBox.setObjectName("xStartSpinBox")
        window.xEndSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.xEndSpinBox.setObjectName("xEndSpinBox")
        window.xStepSpinBox = self._make_spinbox(decimals=4, minimum=0.0001, maximum=1e6)
        window.xStepSpinBox.setObjectName("xStepSpinBox")

        window.yStartSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.yStartSpinBox.setObjectName("yStartSpinBox")
        window.yEndSpinBox = self._make_spinbox(decimals=3, minimum=-1e6, maximum=1e6)
        window.yEndSpinBox.setObjectName("yEndSpinBox")
        window.yStepSpinBox = self._make_spinbox(decimals=4, minimum=0.0001, maximum=1e6)
        window.yStepSpinBox.setObjectName("yStepSpinBox")

        window.scanAveragingTimeSpinBox = self._make_spinbox(decimals=4, minimum=0.0, maximum=1e6)
        window.scanAveragingTimeSpinBox.setObjectName("scanAveragingTimeSpinBox")
        window.scanDwellTimeSpinBox = self._make_spinbox(decimals=4, minimum=0.0, maximum=1e6)
        window.scanDwellTimeSpinBox.setObjectName("scanDwellTimeSpinBox")

        area_grid.addWidget(QtWidgets.QLabel("X Start"), 0, 0)
        area_grid.addWidget(window.xStartSpinBox, 0, 1)
        area_grid.addWidget(QtWidgets.QLabel("X End"), 0, 2)
        area_grid.addWidget(window.xEndSpinBox, 0, 3)
        area_grid.addWidget(QtWidgets.QLabel("X Step"), 0, 4)
        area_grid.addWidget(window.xStepSpinBox, 0, 5)

        area_grid.addWidget(QtWidgets.QLabel("Y Start"), 1, 0)
        area_grid.addWidget(window.yStartSpinBox, 1, 1)
        area_grid.addWidget(QtWidgets.QLabel("Y End"), 1, 2)
        area_grid.addWidget(window.yEndSpinBox, 1, 3)
        area_grid.addWidget(QtWidgets.QLabel("Y Step"), 1, 4)
        area_grid.addWidget(window.yStepSpinBox, 1, 5)

        area_grid.addWidget(QtWidgets.QLabel("Averaging Time"), 2, 0)
        area_grid.addWidget(window.scanAveragingTimeSpinBox, 2, 1)
        area_grid.addWidget(QtWidgets.QLabel("Dwell Time"), 2, 2)
        area_grid.addWidget(window.scanDwellTimeSpinBox, 2, 3)

        sweep_group = QtWidgets.QGroupBox("ODMR Sweep")
        sweep_grid = QtWidgets.QGridLayout(sweep_group)

        window.startFreqBox = self._make_spinbox(decimals=6, minimum=0.0, maximum=20.0)
        window.startFreqBox.setObjectName("startFreqBox")
        window.endFreqBox = self._make_spinbox(decimals=6, minimum=0.0, maximum=20.0)
        window.endFreqBox.setObjectName("endFreqBox")
        window.stepSizeBox = self._make_spinbox(decimals=3, minimum=0.0, maximum=1e9)
        window.stepSizeBox.setObjectName("stepSizeBox")
        window.dwellTimeBox = self._make_spinbox(decimals=4, minimum=0.0, maximum=1e6)
        window.dwellTimeBox.setObjectName("dwellTimeBox")

        window.pointsBox = QtWidgets.QSpinBox()
        window.pointsBox.setObjectName("pointsBox")
        window.pointsBox.setRange(1, 1000000)

        window.sweepDefBox = QtWidgets.QComboBox()
        window.sweepDefBox.setObjectName("sweepDefBox")
        window.sweepDefBox.addItems(["Points", "Step Size"])

        window.odmrSweepContinous = QtWidgets.QCheckBox("Continuous Sweep")
        window.odmrSweepContinous.setObjectName("odmrSweepContinous")

        window.feedbackToggle = QtWidgets.QCheckBox("Enable Feedback")
        window.feedbackToggle.setObjectName("feedbackToggle")
        window.scanAveragingToggle = QtWidgets.QCheckBox("Enable Scan Averaging")
        window.scanAveragingToggle.setObjectName("scanAveragingToggle")
        window.scalarRadio = QtWidgets.QRadioButton("Scalar")
        window.scalarRadio.setObjectName("scalarRadio")
        window.vectorRadio = QtWidgets.QRadioButton("Vector")
        window.vectorRadio.setObjectName("vectorRadio")
        window.scalarRadio.setChecked(True)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(window.scalarRadio)
        mode_layout.addWidget(window.vectorRadio)
        mode_layout.addStretch(1)

        sweep_grid.addWidget(QtWidgets.QLabel("Start Freq (GHz)"), 0, 0)
        sweep_grid.addWidget(window.startFreqBox, 0, 1)
        sweep_grid.addWidget(QtWidgets.QLabel("End Freq (GHz)"), 0, 2)
        sweep_grid.addWidget(window.endFreqBox, 0, 3)
        sweep_grid.addWidget(QtWidgets.QLabel("Step Size (kHz)"), 1, 0)
        sweep_grid.addWidget(window.stepSizeBox, 1, 1)
        sweep_grid.addWidget(QtWidgets.QLabel("Points"), 1, 2)
        sweep_grid.addWidget(window.pointsBox, 1, 3)
        sweep_grid.addWidget(QtWidgets.QLabel("Dwell Time"), 2, 0)
        sweep_grid.addWidget(window.dwellTimeBox, 2, 1)
        sweep_grid.addWidget(QtWidgets.QLabel("Definition"), 2, 2)
        sweep_grid.addWidget(window.sweepDefBox, 2, 3)
        sweep_grid.addWidget(window.odmrSweepContinous, 3, 0, 1, 2)
        sweep_grid.addWidget(window.feedbackToggle, 3, 2, 1, 2)
        sweep_grid.addWidget(window.scanAveragingToggle, 4, 0, 1, 2)
        sweep_grid.addLayout(mode_layout, 4, 2, 1, 2)

        feedback_group = QtWidgets.QGroupBox("Feedback Frequencies")
        feedback_layout = QtWidgets.QVBoxLayout(feedback_group)

        window.scanODMRPropertiesTable = QtWidgets.QTableWidget(4, 2)
        window.scanODMRPropertiesTable.setObjectName("scanODMRPropertiesTable")
        window.scanODMRPropertiesTable.setHorizontalHeaderLabels([
            "Frequency (GHz)",
            "Gradient (V/MHz)",
        ])
        window.scanODMRPropertiesTable.horizontalHeader().setStretchLastSection(True)
        window.scanODMRPropertiesTable.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        window.scanODMRPropertiesTable.verticalHeader().setVisible(False)

        feedback_layout.addWidget(window.scanODMRPropertiesTable)

        layout.addWidget(area_group)
        layout.addWidget(sweep_group)
        layout.addWidget(feedback_group, 1)

        return tab

    def _build_status_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("statusPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        stage_card = QtWidgets.QGroupBox("Stage Status")
        stage_form = QtWidgets.QFormLayout(stage_card)
        window.currentXLabel = QtWidgets.QLabel("-")
        window.currentXLabel.setObjectName("currentXLabel")
        window.currentYLabel = QtWidgets.QLabel("-")
        window.currentYLabel.setObjectName("currentYLabel")
        window.currentHeightLabel = QtWidgets.QLabel("-")
        window.currentHeightLabel.setObjectName("currentHeightLabel")
        stage_form.addRow("X", window.currentXLabel)
        stage_form.addRow("Y", window.currentYLabel)
        stage_form.addRow("Z", window.currentHeightLabel)

        rf_card = QtWidgets.QGroupBox("RF Status")
        rf_form = QtWidgets.QFormLayout(rf_card)
        window.currentFreqLabel = QtWidgets.QLabel("-")
        window.currentFreqLabel.setObjectName("currentFreqLabel")
        window.powerLabel = QtWidgets.QLabel("-")
        window.powerLabel.setObjectName("powerLabel")
        window.modFreqLabel = QtWidgets.QLabel("-")
        window.modFreqLabel.setObjectName("modFreqLabel")
        window.modAmpLabel = QtWidgets.QLabel("-")
        window.modAmpLabel.setObjectName("modAmpLabel")
        rf_form.addRow("Current Freq (GHz)", window.currentFreqLabel)
        rf_form.addRow("Power (dBm)", window.powerLabel)
        rf_form.addRow("Mod Freq (kHz)", window.modFreqLabel)
        rf_form.addRow("Mod Amp (MHz)", window.modAmpLabel)

        layout.addWidget(stage_card)
        layout.addWidget(rf_card)
        layout.addStretch(1)

        return panel

    @staticmethod
    def _build_connection_indicator(window, prefix, label_text):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        dot = QtWidgets.QLabel()
        dot.setObjectName(f"{prefix}ConnectionDot")
        dot.setFixedSize(12, 12)
        dot.setProperty("connectionState", "disconnected")

        label = QtWidgets.QLabel(label_text)
        label.setObjectName(f"{prefix}ConnectionLabel")
        label.setProperty("connectionState", "disconnected")

        setattr(window, f"{prefix}ConnectionDot", dot)
        setattr(window, f"{prefix}ConnectionLabel", label)

        layout.addWidget(dot)
        layout.addWidget(label)
        layout.addStretch(1)
        return container

    @staticmethod
    def _make_spinbox(decimals=3, minimum=-1e9, maximum=1e9):
        box = QtWidgets.QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(minimum, maximum)
        box.setKeyboardTracking(False)
        return box

    @staticmethod
    def _apply_main_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                color: #1f2933;
                background: #f3f5f7;
                font-size: 12px;
            }
            QFrame#headerCard, QFrame#quickActionsCard, QFrame#statusPanel {
                background: #ffffff;
                border: 1px solid #d2d8df;
                border-radius: 10px;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
                color: #0f1720;
            }
            QLabel#subtitleLabel {
                color: #5b6876;
                font-size: 11px;
            }
            QLabel#statusChip {
                background: #e6f7ed;
                color: #17653a;
                border: 1px solid #9fdbb8;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dde5;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334154;
            }
            QTabWidget::pane {
                border: 1px solid #cfd6de;
                border-radius: 8px;
                top: -1px;
                background: #eef1f5;
            }
            QTabBar::tab {
                background: #dfe5ec;
                color: #3c4a5a;
                border: 1px solid #c7d0da;
                padding: 7px 14px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
                font-weight: 600;
            }
            QPushButton {
                background: #1f5a82;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1a4d6f;
            }
            QPushButton:pressed {
                background: #153f5a;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #3f8fc2;
            }
            QLabel[connectionState="connected"] {
                color: #17653a;
                font-weight: 600;
            }
            QLabel[connectionState="connecting"] {
                color: #9a6700;
                font-weight: 600;
            }
            QLabel[connectionState="error"], QLabel[connectionState="disconnected"] {
                color: #8a2432;
                font-weight: 600;
            }
            QLabel#stageConnectionDot, QLabel#rfConnectionDot, QLabel#liaConnectionDot {
                min-width: 12px;
                max-width: 12px;
                min-height: 12px;
                max-height: 12px;
                border-radius: 6px;
                background: #c0392b;
                border: 1px solid #9b2c22;
            }
            QLabel#stageConnectionDot[connectionState="connected"],
            QLabel#rfConnectionDot[connectionState="connected"],
            QLabel#liaConnectionDot[connectionState="connected"] {
                background: #2ea043;
                border: 1px solid #1e7a31;
            }
            QLabel#stageConnectionDot[connectionState="connecting"],
            QLabel#rfConnectionDot[connectionState="connecting"],
            QLabel#liaConnectionDot[connectionState="connecting"] {
                background: #d4a72c;
                border: 1px solid #9a6700;
            }
            QCheckBox, QRadioButton {
                spacing: 6px;
            }
            QTableWidget {
                gridline-color: #dbe2ea;
            }
            QHeaderView::section {
                background: #e8edf2;
                border: none;
                border-right: 1px solid #d4dbe3;
                border-bottom: 1px solid #d4dbe3;
                padding: 5px;
                font-weight: 600;
            }
            """
        )
