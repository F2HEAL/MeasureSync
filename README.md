# MeasureSync

This script synchronizes triggering F2Heal VHP device while making EEG measurements

## Requirements

Python:

- [Brainflow](https://brainflow.readthedocs.io/en/stable/BuildBrainFlow.html#python) package.

VHP:

- The [F2H-SERIAL_COMMAND_2](https://github.com/F2HEAL/VHP-Vibro-Glove2/tree/F2H-SERIAL_COMAND_2) branch

## Usage

A Typical usage would be:

      python '.\sweep_CH_Vol_Freq_diff_ON_OFF.py' -m '.\sweep_CH_Vol_Freq_diff_ON_OFF.yaml' -d .\dev_freeeg.yaml -v

     v1 -m ../conf/vol_sweep10_100_freq_a250.yaml  -d ../conf/dev_playback.yaml

Where
- *vol_sweep10_100_freq_a250.yaml* defines the VHP volumes and frequencies to be measured
- *dev_playback.yaml* defines the EEG device to be used

After completion, the results can be found in the *Recordings* folder

### Measurement configuration

A typical measurement configuration would be:
```
Volume:
  Start: 10
  End: 100
  Steps: 5

Frequency:
  Start: 250
  End: 250
  Steps: 1

Measurements:
  Number: 10  # Number of measurements for each vol/freq combination
  Duration: 1 # Duration in seconds of each measurement
```

The above configuration file will measure every volume between 10 and 100 increased with steps of 5 at the frequency of 250Hz. For every volume-frequency combination 10 measurements of 1 sec will be made.

Other examples are provided in the *conf* folder.

### Device configuration

A typical device configuration file would be:
```
Board:
  Id: EXPLORE_8_CHAN_BOARD
  Master: null
  Mac: "00:13:43:A1:84:FE"
  File: null
  Keep_ble_alive: false

VHP:
  Serial: "/dev/ttyACM0"
  
```

With this configuration file the MentaLab device with Mac 00:13:43:A1:84:FE will be used to stream data from. The VHP device will be addressed through serial port */dev/ttyACM0*

For the above configuration to work, the device running this script would need to be blue-tooth paired with the Mentalab device prior to running the script.

Other examples are provided in the *conf* folder.

```
Board:
  Id: FREEEEG32_BOARD
  Master: null
  Mac: null
  File: null
#  Serial: "/dev/ttyACM1"
  Serial: "COM5"
  Keep_ble_alive: false

VHP:
#  Serial: "/dev/ttyACM0"
  Serial: "COM8"

```

# Measure Report

**measure_report.py** can be used to analyse the results of v1.py. 

The two mandatory arguments are the *file_base* and *output_dir*. For a given *file_base* all CSV files starting with this string will be analysed. The results will be written to *output_dir*.

Typical usage:

``` 
$ python measure_report.py -r -m -v INFO ../May_16th_ML_T/250516-1954_ /tmp/out-mentalab/
[2025-05-18 14:57:41] INFO: Starting program.
[2025-05-18 14:57:41] INFO: Opening ../May_16th_ML_T/250516-1954_EXPLORE_8_CHAN_BOARD_baseline_with_VHP_powered_OFF_on_persons_head_YES_NO.csv
QSocketNotifier: Can only be used with threads started with QThread
Channels marked as bad:
...
```

Check the command line options:

```
usage: measure_report.py [-h] [-v {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-m] [-r] file_base output_dir

EEG Brainflow processing script.

positional arguments:
  file_base             Base file name (input file, without extension).
  output_dir            Directory where output will be written.

options:
  -h, --help            show this help message and exit
  -v, --verbosity {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging verbosity level (default: INFO).
  -m, --mentalab        Enable Mentalab, default FreeEEG32
  -r, --resample        Resample Mentalab based on timestamp

```

