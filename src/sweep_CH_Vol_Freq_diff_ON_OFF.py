# sweep CH Vol Freq diff ON OFF

#!/usr/bin/env python

import argparse
import logging
import time
from datetime import datetime
import serial
import yaml
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


class Config:
    """Holds information from parsed config files"""

    def __init__(self, measurement, device, args):
        self.channel_start = measurement['Channel']['Start']
        self.channel_end = measurement['Channel']['End']
        self.channel_steps = measurement['Channel']['Steps']
        self.volume_start = measurement['Volume']['Start']
        self.volume_end = measurement['Volume']['End']
        self.volume_steps = measurement['Volume']['Steps']
        self.frequency_start = measurement['Frequency']['Start']
        self.frequency_end = measurement['Frequency']['End']
        self.frequency_steps = measurement['Frequency']['Steps']
        self.measurements_number = measurement['Measurements']['Number']
        self.measurements_duration_on = measurement['Measurements']['Duration_on']
        self.measurements_duration_off = measurement['Measurements']['Duration_off']
        self.measurements_prestart = measurement['Measurements']['Pre-start_EEG_measurement']
        self.board_id = device['Board']['Id']
        self.board_master = device['Board']['Master']
        self.board_mac = device['Board']['Mac']
        self.board_file = device['Board']['File']
        self.board_serial = device['Board']['Serial']
        self.keep_ble_alive = device['Board']['Keep_ble_alive']
        self.serial_port = device['VHP']['Serial']
        self.verbose = args.verbose
        self.timestamp = datetime.now().strftime("%y%m%d-%H%M")

    def __str__(self):
        return (f"Volume Range: {self.volume_start} to {self.volume_end}, "
                f"Steps: {self.volume_steps}\n"
                f"Frequency Range: {self.frequency_start} to "
                f"{self.frequency_end}, Steps: {self.frequency_steps}\n"
                f"Measurements: Number = {self.measurements_number}, "
                f"Duration_on = {self.measurements_duration_on}s, "
                f"Duration_off = {self.measurements_duration_off}s\n"
                f"Board: Id = {self.board_id}, Master = {self.board_master}, "
                f"Mac = {self.board_mac}, Serial = {self.board_serial}")


class SerialCommunicator:
    """Handles serial communication with VHP device"""

    BAUDRATE = 115200
    TIMEOUT_SEC = 1

    def __init__(self, port):
        self.port = port
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.BAUDRATE,
            timeout=self.TIMEOUT_SEC
        )
        if not self.ser.is_open:
            self.ser.open()

        # Wait a bit for Arduino reset
        time.sleep(2)

    def __del__(self):
        if hasattr(self, 'ser'):
            if self.ser.is_open:
                self.ser.close()
                logging.info("Serial closed")

    def _send_command(self, command):
        self.ser.write((command + '\n').encode('utf-8'))
        logging.debug("Serial VHP Sent: %s", command)

        # Wait a little to receive Arduino reply
        time.sleep(0.05)

        # Read and print all available replies
        while self.ser.in_waiting > 0:
            response = self.ser.readline().decode('utf-8', errors='ignore').strip()
            logging.debug("Serial VHP Received: %s", response)

    def set_duration(self, duration):
        duration = max(1, min(65535, duration))
        self._send_command(f'D{duration}')

    def set_cycle_period(self, cycle_period):
        cycle_period = max(1, min(65535, cycle_period))
        self._send_command(f'Y{cycle_period}')

    def set_pause_cycle_period(self, pause_cycle_period):
        pause_cycle_period = max(0, min(100, pause_cycle_period))
        self._send_command(f'P{pause_cycle_period}')

    def set_paused_cycles(self, paused_cycles):
        paused_cycles = max(0, min(100, paused_cycles))
        self._send_command(f'Q{paused_cycles}')

    def set_jitter(self, jitter):
        jitter = max(0, min(1000, jitter))
        self._send_command(f'J{jitter}')

    def set_test_mode(self, enabled):
        self._send_command(f'M{1 if enabled else 0}')

    def set_channel(self, channel):
        channel = max(0, min(8, channel))
        self._send_command(f'C{channel}')

    def set_volume(self, volume):
        volume = max(0, min(100, volume))
        self._send_command(f'V{volume}')

    def set_frequency(self, frequency):
        self._send_command(f'F{frequency}')

    def start_stream(self):
        self._send_command('1')

    def stop_stream(self):
        self._send_command('0')

    def get_fw(self):
        self._send_command('S')

    def get_par(self):
        self._send_command('X')

def parse_yaml_file(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)


def parse_cmdline():
    parser = argparse.ArgumentParser(description="EEG/VHP sync")
    parser.add_argument('-m', '--measureconf', type=str, required=True,
                        help="Path to the YAML measurement configuration file")
    parser.add_argument('-d', '--deviceconf', type=str, required=True,
                        help="Path to the YAML measurement device"
                        "configuration file")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="verbose level, up until 5 allowed")
    args = parser.parse_args()

    # Parse the specified YAML file
    measurement = parse_yaml_file(args.measureconf)

    device = parse_yaml_file(args.deviceconf)

    config = Config(measurement, device, args)

    return args, config


def setup_brainflow_board(config):

    params = BrainFlowInputParams()

    if config.board_master:
        # Setup for playback device
        params.file = config.board_file
        params.master_board = BoardIds[config.board_master].value
        board_id = BoardIds[config.board_id].value
    else:
        # Setup for live streaming
        if config.board_mac:
            params.mac_address = config.board_mac

        if config.board_serial:
            params.serial_port = config.board_serial

        board_id = BoardIds[config.board_id]

    board_shim = BoardShim(board_id, params)

    return board_shim


def do_measurement(com, board_shim, config, channel, frequency, volume):
    logging.info("Measuring Chan=%i Freq=%i Vol=%i", channel, frequency, volume)

    fname = (f"./Recordings/{config.timestamp}_{config.board_id}_"
             f"c{channel}_f{frequency}_v{volume}.csv")

    streamer_params = f"file://{fname}:w"
    board_shim.add_streamer(streamer_params) #start writing to file

    time.sleep(0.002)

    board_shim.insert_marker(333) # insert "creating baseline until 1st stimulus_ON, with VHP powered ON" marker

    time.sleep(config.measurements_prestart)

    for i in range(config.measurements_number):
        board_shim.insert_marker(1) # insert stimulus_ON marker
        com.start_stream()

        time.sleep(config.measurements_duration_on)

        board_shim.insert_marker(11) # insert stimulus_OFF marker
        com.stop_stream()

        time.sleep(config.measurements_duration_off)

    board_shim.delete_streamer(streamer_params) #stop writing to file

def write_metadata(args, config, fname1):
    fname = (f"./Recordings/{config.timestamp}_metadata.txt")
    with open(fname, "w") as f:
        readable_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        f.write(f"Recording on: {readable_timestamp}\n")
        f.write("\n")
        f.write("Subject name: \n")
        f.write("Recording location: \n")
        f.write("finger tested: \n\n")
        f.write("S/N VBS device: \n")
        f.write("BLE MAC VBS device:  C6:3F:B3:3E:8A:72 \n")

        f.write("Modelname VBS device: F2Heal VHP vSERCOM_2_0_0_BETA \n")

        f.write("\n")

        f.write("*** Contents of Measure Configuration ***\n")
        fm = open(args.measureconf, "r")
        f.write(fm.read())

        f.write("*** Contents of Device Configuration:***\n")
        fd = open(args.deviceconf, "r")
        f.write(fd.read())
        f.write("\n")
        f.write(f"EEG measurements baseline with VHP powered OFF {fname1} \n")
                 

def is_vhp_connected(port, baudrate=115200, timeout=1):
    try:
        with serial.Serial(port, baudrate=baudrate, timeout=timeout) as ser:
            time.sleep(1)  # wait for possible board reset
            return True
    except (serial.SerialException, OSError):
        return False
    
# Function to keep BLE link alive
def keep_ble_alive(board_shim, interval=1):
    while True:
        try:
            board_shim.get_board_data()
            time.sleep(interval)
        except Exception as e:
            logging.warning(f"BLE keepalive thread error: {e}")
            break

def main():
    fname1 = "no power OFF VHP CYCLE"
    args, config = parse_cmdline()

    BoardShim.enable_dev_board_logger()

    logging.basicConfig(
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        level=config.verbose*10)  # doesn't work?
    logging.info("Config loaded: %s", config)

    # Connect to board
    board_shim = setup_brainflow_board(config)
    # Prepare session before streaming
    board_shim.prepare_session()
    board_shim.start_stream()    # start eeg stream  

    if config.keep_ble_alive:
        logging.info("Starting BLE keep-alive thread...")
        from threading import Thread
        Thread(target=keep_ble_alive, args=(board_shim,), daemon=True).start()

    try:
        if not is_vhp_connected(config.serial_port):

            # Create unique file for EEG measurements baseline with VHP powered OFF
            fname1 = f"./Recordings/{config.timestamp}_{config.board_id}_baseline_with_VHP_powered_OFF_on_persons_head_YES_NO.csv"
            streamer_params = f"file://{fname1}:w"

            board_shim.add_streamer(streamer_params) #start writing to file

            time.sleep(0.003)
            board_shim.insert_marker(3) # insert VHP_OFF marker

            while not is_vhp_connected(config.serial_port):
                print("While waiting for VHP board, EEG _baseline_with_VHP_powered_OFF_on_persons_head_YES_NO.csv is being recorded...")
                print("Switch VHP board ON after few seconds.")
                time.sleep(2)

            print("VHP board is powered ON / connected.")
            board_shim.insert_marker(33) # insert VHP_ON marker
            time.sleep(config.measurements_prestart)
            board_shim.delete_streamer(streamer_params) # stop writing to file

        vhpcom = SerialCommunicator(config.serial_port)

        vhpcom.set_duration(8000)
        vhpcom.set_cycle_period(64000)
        vhpcom.set_pause_cycle_period(1)
        vhpcom.set_paused_cycles(0)
        vhpcom.set_jitter(0)
        vhpcom.set_test_mode(1)
   
        for chan in range(config.channel_start, config.channel_end + 1,
                          config.channel_steps):
            for freq in range(config.frequency_start, config.frequency_end + 1,
                              config.frequency_steps):
                for vol in range(config.volume_start, config.volume_end+1,
                                 config.volume_steps):



                    vhpcom.set_channel(chan)
                    vhpcom.set_volume(vol)
                    vhpcom.set_frequency(freq)

                    do_measurement(vhpcom, board_shim, config,
                                   chan, freq, vol)

        board_shim.stop_stream()
        board_shim.release_session()
        print("Stream stopped and session released.")
        
        write_metadata(args, config, fname1)

    except BaseException as e:
        logging.warning('Exception', exc_info=True)
        print(f"Error: {e}")
        if board_shim.is_prepared():
            board_shim.stop_stream()
            board_shim.release_session()
    finally:
        if board_shim.is_prepared():
            logging.info('Releasing session')
            board_shim.release_session()


if __name__ == "__main__":
    main()
