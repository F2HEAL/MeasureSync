# MeasureSync

This script synchronizes triggering F2Heal VHP device while making EEG measurements

# Requirements

Python:

- [Brainflow](https://brainflow.readthedocs.io/en/stable/BuildBrainFlow.html#python) package.

VHP:

- The [F2H-SERIAL_COMMAND](https://github.com/F2HEAL/VHP-Vibro-Glove2/tree/F2H-SERIAL_COMAND) branch

# Usage

A Typical usage would be:

     v1 -m ../conf/vol_sweep10_100_freq_a250.yaml  -d ../conf/dev_playback.yaml

Where
- *vol_sweep10_100_freq_a250.yaml* defines the VHP volumes and frequencies to be measured
- *dev_playback.yaml* defines the EEG device to be used

After completion, the results can be found in the *Recordings* folder

## Measurement configuration

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

## Device configuration

A typical device configuration file would be:
```
Board:
  Id: EXPLORE_8_CHAN_BOARD
  Master: null
  Mac: "00:13:43:A1:84:FE"
  File: null

VHP:
  Serial: "/dev/ttyACM0"
  
```

With this configuration file the MentaLab device with Mac 00:13:43:A1:84:FE will be used to stream data from. The VHP device will be addressed through serial port */dev/ttyACM0*

For the above configuration to work, the device running this script would need to be blue-tooth paired with the Mentalab device prior to running the script.

Other examples are provided in the *conf* folder.

