# Scanning Magnetometry Software Documentation

---

## 1. Overview

<!-- Brief description of the software purpose and context -->

### 1.1 What This Software Does

### 1.2 High-Level Measurement Workflow

### 1.3 Supported Hardware

- **XY Motorised Stage:**
- **RF Source:**
- **Lock-In Amplifier (LIA):**

---

## 2. Installation & Setup

### 2.1 Requirements

- Python version:
- Dependencies: see `requirements.txt` / `packagelist.txt`

### 2.2 Setting Up the Virtual Environment

```bash
# Example
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.3 Optional: Dark Theme

<!-- qdarktheme — installed separately, falls back gracefully if missing -->

### 2.4 Running the Application

```bash
python main.py
```

---

## 3. Configuration Files

### 3.1 Config File Format

<!-- YAML format overview -->

### 3.2 Config Keys Reference

| Section | Key | Type | Description | Default |
|---|---|---|---|---|
| `Connection_Params` | `Device_ID` | string | Zurich LIA device ID | `dev7811` |
| `Connection_Params` | `Device_IP` | string | Zurich LIA IP address | `192.168.1.101` |
| `Connection_Params` | `RF_IP` | string | RF source IP address | `192.168.1.2` |
| `LIA_Params` | `Time_Const` | float (µs) | LIA time constant | `600` |
| `LIA_Params` | `Sample_Rate` | int | DAQ sample rate | `50` |
| `LIA_Params` | `Filter_Order` | int | Demod filter order | `7` |
| `LIA_Params` | `Scaling` | float | Voltage scaling factor | `750` |
| `LIA_Params` | `Duration` | float (s) | Sweep acquisition duration | `10` |
| `LIA_Params` | `Burst_Dur` | float (s) | Burst mode duration | `0.005` |
| `LIA_Params` | `Range` | int | Input range setting | `0` |
| `LIA_Params` | `FFT_Sample_Rate` | int | FFT window sample rate | `2048` |
| `LIA_Params` | `FFT_Duration` | float (s) | FFT acquisition duration | `1` |
| `LIA_Params` | `FFT_Average` | int | FFT averages | `5` |
| `LIA_Params` | `FFT_50_Ohm` | bool | 50 Ω input termination | `False` |
| `LIA_Params` | `FFT_AC_Coupling` | bool | AC coupling for FFT | `False` |
| `RF_Params` | `Freq` | float (GHz) | RF centre frequency | `2.75` |
| `RF_Params` | `Power` | float (dBm) | RF output power | `-30` |
| `RF_Params` | `Power_On` | bool | RF output enabled | `False` |
| `RF_Params` | `Mod_On` | bool | Modulation enabled | `True` |
| `RF_Params` | `Mod_Type` | int | Modulation type | `1` |
| `RF_Params` | `Mod_Freq` | float (kHz) | Modulation frequency | `3.05` |
| `RF_Params` | `Mod_Amp` | float | Modulation amplitude | `2.8` |
| `RF_Params` | `Ext_Mod` | bool | External modulation | `False` |
| `RF_Params` | `Feedback_Freq_Table` | list | Resonance freq/grad pairs | — |
| `RF_Params` | `A_Matrix_Values` | list | Vector A-matrix | — |
| `Stage_Params` | `X_Start` | float (µm) | Scan X start | `10` |
| `Stage_Params` | `X_End` | float (µm) | Scan X end | `20` |
| `Stage_Params` | `X_Step` | float (µm) | Scan X step size | `1` |
| `Stage_Params` | `Y_Start` | float (µm) | Scan Y start | `10` |
| `Stage_Params` | `Y_End` | float (µm) | Scan Y end | `20` |
| `Stage_Params` | `Y_Step` | float (µm) | Scan Y step size | `1` |
| `Stage_Params` | `Dwell` | float (s) | Stage settle dwell time | `0.05` |
| `Stage_Params` | `Avg_Time` | float (s) | Averaging time per pixel | `0.1` |
| `Sweep_Params` | `Sweep_Start` | float (GHz) | Sweep start frequency | `2.7` |
| `Sweep_Params` | `Sweep_End` | float (GHz) | Sweep end frequency | `3.0` |
| `Sweep_Params` | `Points` | int | Number of sweep points | `1000` |
| `Sweep_Params` | `Sweep_Step` | float (kHz) | Step size (step-size mode) | `250` |
| `Sweep_Params` | `Sweep_Type` | int | Sweep mode (1=points, 2=step) | `1` |
| `Sweep_Params` | `Dwell` | float (s) | Per-point dwell time | `3.0` |

### 3.3 Loading and Saving Configs from the UI

### 3.4 The `settings.yml` File

<!-- Auto-saved last-used values -->

---

## 4. Instrument Connections

### 4.1 Motorised Stage

<!-- Serial/COM port connection, baud rate, port selection -->

### 4.2 RF Source

<!-- TCPIP/PyVISA connection, manual IP entry, discovered IP dropdown -->

### 4.3 Lock-In Amplifier (Zurich Instruments)

<!-- zhinst connection, device ID and IP, manual vs. discovered dropdowns -->

### 4.4 Auto Discover IPs Button

<!-- What is probed (port 5025 socket scan + zhinst discovery), when to use it -->

---

## 5. Main Window Reference

### 5.1 Connection Tab

#### Stage Connection

#### RF Source Connection

#### LIA Connection

### 5.2 LIA Settings

<!-- Time constant, sample rate, filter order, scaling factor, reference type, demod settings -->

### 5.3 RF Settings

<!-- Frequency, power, modulation, sweep mode (point-count vs. step-size) -->

### 5.4 Stage / Scan Settings

<!-- X/Y start, end, step; dwell time; averaging time -->

### 5.5 ODMR Resonance Table

<!-- scanODMRPropertiesTable — resonance frequency and gradient pairs, used by scanning and vector feedback -->

### 5.6 Quick Actions

<!-- Auto Discover, open windows, start/stop LIA live trace -->

---

## 6. Measurement Modes

### 6.1 ODMR Frequency Sweep

#### What It Measures

#### Trigger Flow

<!-- RF setup → LIA synchronised DAQ → sweep acquire -->

#### Frequency Axis

<!-- Point-count mode vs. step-size mode; effective axis derivation; instrument-reported point count query -->

#### ODMR Graph Window

- Live plot
- Linear-region selection
- Gradient fitting
- Sending resonance/gradient to the feedback table

### 6.2 Spatial Scan

#### Scalar Scan Mode

<!-- Single-resonance proportional feedback per pixel -->

#### Vector Scan Mode

<!-- Four-resonance tracking per pixel; B-vector component image -->

#### Scan Flow

<!-- Stage step → RF hop → settle → LIA read → correct → store -->

#### Saving and Exporting

<!-- HDF5 output format, image export -->

### 6.3 LIA Live Trace

<!-- Real-time display of demodulated signal (X and/or R) -->

### 6.4 FFT / Sensitivity Window

<!-- Sample rate, averaging, 50 Ω / AC coupling settings -->

---

## 7. Vector Resonance Tracking

### 7.1 Overview

<!-- Continuously tracks up to 4 ODMR resonance frequencies in real time using closed-loop feedback -->

### 7.2 Tracking Modes

- **Four resonances**: all four entries in the ODMR table must be populated
- **Single resonance**: only the selected resonance is updated; others are cleared

### 7.3 Demod Feedback Signal

- **X**: raw in-phase demodulated signal
- **R**: magnitude = √(x² + y²) via `np.hypot(x, y)` — more robust to phase drift

### 7.4 Control Loop

#### Setpoint Initialisation

<!-- Baseline voltage measured at each resonance frequency just before tracking begins; used as per-resonance setpoint throughout run -->

#### Proportional Mode

<!-- df = −dV / gradient -->

#### PID Mode

<!-- df = Kp·e + Ki·∫e dt + Kd·de/dt; per-resonance integrator with anti-windup clamp -->

#### Baseline Adaptation

<!-- Exponential moving average on the setpoint: ini_voltage = (1−α)·ini_voltage + α·voltage_now
     Small α compensates slow drift; large α risks masking real shifts -->

#### Deadband

<!-- Corrections suppressed when |dV| < threshold, prevents noise-driven jitter -->

#### Output Clamping

<!-- max_df_step_mhz: maximum per-iteration frequency correction
     max_tracking_offset_mhz: maximum total deviation from starting frequency -->

### 7.5 UI Controls Reference

| Control | Description | Units | Guidance |
|---|---|---|---|
| Tracking mode | Four or single resonance | — | |
| Tracked resonance | Which resonance to use in single mode | — | |
| Demod feedback | X or R signal used for error | — | R recommended for phase robustness |
| Avg samples | Number of LIA samples averaged per read | — | Higher = less noise, slower loop |
| Sample spacing | Delay between averaged samples | s | |
| Max df step | Maximum per-step frequency correction | MHz | Start small to avoid runaway |
| Max tracking offset | Maximum total shift from start frequency | MHz | |
| Plot update interval | Minimum time between graph redraws | s | |
| Use scaled LIA voltage | Apply instrument scaling factor to signal | — | |
| Deadband \|dV\| | Correction suppressed below this voltage error | V | |
| Enable baseline adaptation | Slowly update setpoint to follow drift | — | |
| Baseline adapt alpha | EMA coefficient for setpoint drift | — | Typical: 0.001–0.01 |
| Control mode | Proportional or PID | — | Start proportional, tune to PID |
| PID Kp | Proportional gain | — | Start at 1.0 |
| PID Ki | Integral gain | — | Start at 0, add slowly |
| PID Kd | Derivative gain | — | Add only if oscillating |
| PID integral limit | Anti-windup clamp on integral accumulator | MHz·s | |

### 7.6 Live Diagnostics Panel

| Column | Description |
|---|---|
| dV | Voltage error relative to setpoint |
| df (MHz) | Frequency correction applied this iteration |
| Deadband | Whether correction was suppressed by deadband |
| P | Proportional term (PID mode) |
| I | Integral term (PID mode) |
| D | Derivative term (PID mode) |

### 7.7 Plots

- **Top graph**: Frequency shift from start (MHz) vs. iteration index — scrolling history
- **Bottom graph**: Measured demod voltage vs. iteration index — scrolling history

### 7.8 Start / Stop Flow

<!-- Start Tracking: re-reads resonance table, captures setpoints, launches worker thread
     Stop Tracking: sets scanning flag to False, loop exits cleanly, buttons reset
     Window close: calls stop_tracking() automatically -->

---

## 8. Data Viewer

### 8.1 Opening Saved Scan Files

<!-- HDF5 .h5 files; open via UI button -->

### 8.2 Navigating Scan Images

### 8.3 Exporting Data

---

## 9. Developer Guide

### 9.1 Architecture Overview

| Module | Class(es) | Responsibility |
|---|---|---|
| `main.py` | `MainUI` | Main window, instrument wiring, config load/save |
| `main.py` | `VectorTest` | Real-time resonance tracking window and loop |
| `main.py` | `VectorMatrixWindow` | Displays computed B-vector matrix values |
| `main.py` | `StageOptions` | Stage motion parameter window |
| `windows/scanning_window.py` | `scanningImageWindow` | XY scan execution and image display |
| `windows/odmr_window.py` | `ODMRGraphWindow` | ODMR sweep plot, region selection, gradient fitting |
| `windows/fft_window.py` | `FFTGraphWindow` | FFT/sensitivity measurement |
| `windows/lia_live_trace_window.py` | `LIALiveTraceWindow` | Real-time LIA signal monitor |
| `rf_control.py` | `RfControl` | RF source SCPI commands, sweep axis calculation |
| `lia_control.py` | `LIAControl` | Zurich LIA connection, DAQ sweep, runtime settings |
| `stage_control.py` | `StageControl` | Serial stage motion commands |
| `threading_utils.py` | `Worker`, `ThreadedComponent` | Qt thread pool worker pattern |
| `analysis/odmr_fit.py` | — | ODMR peak fitting functions |
| `ui_theme.py` | — | pyqtgraph styling helpers |
| `main_window_ui.py` | `MainWindowUIBuilder` | Programmatic main window UI layout |
| `windows/*_ui.py` | `*UIBuilder` | Programmatic secondary window UI layouts |
| `data_viewer.py` | — | HDF5 scan file viewer |

### 9.2 Threading Pattern

<!-- All hardware operations run through ThreadedComponent.thread_function().
     Worker wraps fn in a QRunnable, routes progress/results/errors through Qt signals.
     UI updates happen only on the main thread via progress_callback.emit(). -->

### 9.3 UI Construction Pattern

<!-- No .ui files; all layouts built programmatically in *UIBuilder classes.
     Each builder exposes a setup(window) method that attaches widgets as attributes of the window object. -->

### 9.4 Effective Sweep Axis

<!-- RfControl.frequency_axis is computed after setup_sweep():
     - Point-count mode: linspace(start, stop, points)
     - Step-size mode: estimated from step size, then verified via :SWE:POINTS? instrument query
     LIAControl.setup_sweep() uses RfControl.num_points to align DAQ count. -->

### 9.5 Data Flow Diagram

```
┌─────────┐   serial    ┌───────────────┐
│  Stage  │────────────▶│  StageControl │
└─────────┘             └──────┬────────┘
                               │ position commands
┌──────────┐  PyVISA   ┌───────▼────────┐
│ RF Source│◀──────────│  RfControl     │
└──────────┘           └──────┬─────────┘
                               │ frequency axis
┌──────────┐  zhinst   ┌───────▼────────┐
│   LIA    │◀──────────│  LIAControl    │
└──────────┘           └──────┬─────────┘
                               │ demod data
                       ┌───────▼────────┐
                       │ scanning_window│
                       │ odmr_window    │
                       │ VectorTest     │
                       └──────┬─────────┘
                               │
                       ┌───────▼────────┐
                       │  HDF5 / plots  │
                       └────────────────┘
```

### 9.6 Adding a New Hardware Backend

1. Create a new controller class (e.g. `my_instrument.py`) following the `RfControl` / `LIAControl` pattern.
2. Add a class instance to `MainUI.__init__` (e.g. `self.myInstrumentController`).
3. Add connection UI in `main_window_ui.py` (`MainWindowUIBuilder`).
4. Wire connect/disconnect logic in `MainUI` using `thread_function()` for long-running operations.

### 9.7 Config Schema — Full Annotated Reference

<!-- Expand on the table in Section 3.2 with valid ranges and behavioural notes -->

---

## 10. Troubleshooting

### Device Not Discovered

<!-- Check IP subnet, firewall, port 5025 access. Use manual IP entry as fallback. Use Auto Discover only after LAN is confirmed reachable. -->

### ODMR X-Axis Mismatch

<!-- Cause: sweep mode mismatch between RF and LIA DAQ point count.
     Fix: ensure Sweep_Type and Points/Sweep_Step values are consistent; effective axis is computed from instrument-reported :SWE:POINTS? -->

### Vector Tracking Runaway

<!-- Check gradient sign for each resonance — they should not all be the same sign in 4-resonance mode.
     Start with Proportional mode, small max_df_step_mhz (e.g. 0.1 MHz), and max_tracking_offset_mhz around 5 MHz.
     Enable deadband to suppress noise-driven corrections.
     Check demod feedback mode: R is more stable than X under phase drift. -->

### PID Oscillation

<!-- Reduce Kd and Ki first. Ensure dt between loop iterations is stable (increases with avg_samples × sample_spacing). -->

### Thread Crash on Window Close

<!-- Worker is stopped via scanning = False flag inside stop_tracking() / closeEvent().
     The worker thread exits the while loop on the next iteration. Allow ~1 loop iteration before the window fully clears. -->

### Stage Not Moving

<!-- Check COM port selection. Verify baud rate matches stage controller firmware.  -->
