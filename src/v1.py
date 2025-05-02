#!/usr/bin/env python

import argparse
import yaml
import logging
import serial
import time
from datetime import datetime
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


class Config:
    def __init__(self, volume_start, volume_end, volume_steps,
                 frequency_start, frequency_end, frequency_steps,
                 measurements_number, measurements_duration,
                 board_id, board_master, board_mac, board_file,
                 serial_port,
                 verbose):
        self.volume_start = volume_start
        self.volume_end = volume_end
        self.volume_steps = volume_steps
        self.frequency_start = frequency_start
        self.frequency_end = frequency_end
        self.frequency_steps = frequency_steps
        self.measurements_number = measurements_number
        self.measurements_duration = measurements_duration
        self.board_id = board_id
        self.board_master = board_master
        self.board_mac = board_mac
        self.board_file = board_file
        self.serial_port = serial_port
        self.verbose = verbose
        self.timestamp = datetime.now().strftime("%y%m%d-%H%M")

    def __str__(self):
        return (f"Volume Range: {self.volume_start} to {self.volume_end}, Steps: {self.volume_steps}\n"
                f"Frequency Range: {self.frequency_start} to {self.frequency_end}, Steps: {self.frequency_steps}\n"
                f"Measurements: Number = {self.measurements_number}, Duration = {self.measurements_duration}s\n"
                f"Board: Id = {self.board_id}, Master = {self.board_master}, Mac = {self.board_mac}")

    def generate_filename_base(self):
        return (f"{self.timestamp}_{self.board_id}_"
                f"vol{self.volume_start}-{self.volume_end}-s{self.volume_steps}_"
                f"freq-{self.frequency_start}-{self.frequency_end}-s{self.frequency_steps}_"
                f"dur-{self.measurements_duration}")


class SerialCommunicator:
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

    def send_command(self, command):
        self.ser.write((command + '\n').encode('utf-8'))
        logging.debug(f"Serial Sent: {command}")

        # Wait a little to receive Arduino reply
        time.sleep(0.05)

        # Read and print all available replies
        while self.ser.in_waiting > 0:
            response = self.ser.readline().decode('utf-8', errors='ignore').strip()
            logging.debug(f"Serial Received: {response}")

    def set_volume(self, volume):
        volume = max(0, min(100, volume))
        self.send_command(f'V{volume}')

    def set_frequency(self, frequency):
        self.send_command(f'F{frequency}')

    def start_stream(self):
        self.send_command('1')

    def stop_stream(self):
        self.send_command('0')


def parse_yaml_file(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def parse_cmdline():
    parser = argparse.ArgumentParser(description="Parse a YAML configuration file.")
    parser.add_argument('-m', '--measureconf', type=str, required=True,
                        help="Path to the YAML measurement configuration file")
    parser.add_argument('-d', '--deviceconf', type=str, required=True,
                        help="Path to the YAML measurement device configuration file")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="verbose level, up until 5 allowed")
    args = parser.parse_args()

    # Parse the specified YAML file
    measurement = parse_yaml_file(args.measureconf)

    device = parse_yaml_file(args.deviceconf)

    # Create a Config object
    config = Config(
        volume_start=measurement['Volume']['Start'],
        volume_end=measurement['Volume']['End'],
        volume_steps=measurement['Volume']['Steps'],
        frequency_start=measurement['Frequency']['Start'],
        frequency_end=measurement['Frequency']['End'],
        frequency_steps=measurement['Frequency']['Steps'],
        measurements_number=measurement['Measurements']['Number'],
        measurements_duration=measurement['Measurements']['Duration'],
        board_id=device['Board']['Id'],
        board_master=device['Board']['Master'],
        board_mac=device['Board']['Mac'],
        board_file=device['Board']['File'],
        serial_port=device['VHP']['Serial'],
        verbose=args.verbose
    )

    BoardShim.enable_dev_board_logger()

    log_format = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"

    logging.basicConfig(
        format=log_format,
        level=config.verbose*10)

    return config

def setup_brainflow_board(config):

    params = BrainFlowInputParams()

    if config.board_master:
        # Setup for playback device
        params.file = config.board_file
        params.master_board = BoardIds[config.board_master].value
        board_id = BoardIds[config.board_id].value
    else:
        # Setup for live streaming
        params.mac_address = config.board_mac
        board_id = BoardIds[config.board_id].value

    board_shim = BoardShim(board_id, params)

    return board_shim

def do_measurement(com, board_shim, config, frequency, volume):
    logging.info(f"Measuring {frequency}-{volume}")

    for i in range(config.measurements_number):
        board_shim.insert_marker(i+1)

        com.start_stream()

        time.sleep(config.measurements_duration)

        com.stop_stream()

        time.sleep(1)

def main():
    config = parse_cmdline()
    logging.info("Config loaded: %s", config)

    # Connect to board
    board_shim = setup_brainflow_board(config)
    try:
        com = SerialCommunicator(config.serial_port)

        board_shim.prepare_session()

        for freq in range(config.frequency_start, config.frequency_end + 1,
                          config.frequency_steps):
            for vol in range(config.volume_start, config.volume_end+1,
                             config.volume_steps):

                # set volume and frequency
                com.set_volume(vol)
                com.set_frequency(freq)

                fname = (f"../Recordings/{config.timestamp}_{config.board_id}_"
                         f"f{freq}_v{vol}.csv")

                streamer_params = f"file://{fname}:w"
                board_shim.add_streamer(streamer_params)
                board_shim.start_stream()

                do_measurement(com, board_shim, config,
                               freq, vol)

                board_shim.stop_stream()
                board_shim.delete_streamer(streamer_params)
    except BaseException:
        logging.warning('Exception', exc_info=True)
    finally:
        if board_shim.is_prepared():
            logging.info('Releasing session')
            board_shim.release_session()


if __name__ == "__main__":
    main()
