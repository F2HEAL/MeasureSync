"""Intended for reporting on results from MeasureSync"""

import argparse
import logging
import os
import sys

import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd


class Config:
    """Configuration holder for command line arguments and validation."""

    def __init__(self):
        args = self.parse_args()
        self.file_base = args.file_base
        self.output_dir = args.output_dir
        self.verbosity = args.verbosity
        self.mentalab = args.mentalab
        self.resample = args.resample

        self.setup_logging()
        self._validate_and_prepare()

    @staticmethod
    def parse_args():
        """Parse and return command line arguments."""
        parser = argparse.ArgumentParser(description="EEG Brainflow processing script.")
        parser.add_argument(
            "file_base",
            type=str,
            help="Base file name (input file, without extension).",
        )
        parser.add_argument(
            "output_dir", type=str, help="Directory where output will be written."
        )
        parser.add_argument(
            "-v",
            "--verbosity",
            type=str,
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default="INFO",
            help="Logging verbosity level (default: INFO).",
        )
        parser.add_argument(
            "-m",
            "--mentalab",
            action="store_true",
            help="Enable Mentalab, default FreeEEG32",
        )
        parser.add_argument(
            "-r",
            "--resample",
            action="store_true",
            help="Resample Mentalab based on timestamp",
        )

        return parser.parse_args()

    def setup_logging(self):
        """Set up the logging configuration."""
        numeric_level = getattr(logging, self.verbosity.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {self.verbosity}")
        logging.basicConfig(
            level=numeric_level,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logging.info("Starting program.")

    def get_matching_csv_files(self):
        """
        Return a list of CSV files in the directory containing file_base that start with
        the same base name (excluding directory) and have a .csv extension.

        Parameters
        ----------
        file_base : str
            The base path (possibly including directory) to match files against.

        Returns
        -------
        list of str
            Sorted list of full paths to matching CSV files.
        """
        directory = os.path.dirname(self.file_base) or "."
        base_prefix = os.path.basename(self.file_base)
        found_files = []

        if not os.path.isdir(directory):
            logging.error("Directory '%s' does not exist.", directory)
            return []

        try:
            for fname in os.listdir(directory):
                if fname.startswith(base_prefix) and fname.lower().endswith(".csv"):
                    full_path = os.path.join(directory, fname)
                    found_files.append(full_path)
                    found_files.sort()
            if not found_files:
                logging.warning(
                    "No matching CSV files found for file base '%s'.", self.file_base
                )
            else:
                logging.debug(
                    "Found %d matching CSV file(s): %s", len(found_files), found_files
                )
            return found_files
        except Exception as exc:
            logging.error("Error when searching for matching files: %s", exc)
            return []

    def _validate_and_prepare(self):
        """Validate input file and output directory, create output dir if needed."""

        if not self.get_matching_csv_files():
            sys.exit(1)

        if not os.path.isdir(self.output_dir):
            try:
                os.makedirs(self.output_dir, exist_ok=True)
                logging.info("Created output directory: %s", self.output_dir)
            except Exception as e:
                logging.error("Could not create output directory: %s", e)
                sys.exit(1)


class EEGCSVLoader:
    """Loads EEG data from a FreeEEG32 CSV and converts to MNE Raw object."""

    CHANNEL_TYPES = ["eeg"] * 8 + ["stim"]
    EVENT_ID = {"ON": 1, "OFF": 11}
    DPI = 300

    def __init__(self, cfg, filename, fmin, fmax):
        self.filename = filename
        self.fmin = fmin
        self.fmax = fmax

        self.out_base = cfg.output_dir + os.path.splitext(os.path.basename(filename))[0]
        self.mentalab = cfg.mentalab
        self.resample = cfg.resample

        if self.mentalab:
            self.channel_names = [
                "CP3",
                "CP4",
                "C2",
                "C6",
                "C1",
                "C4",
                "C3",
                "C5",
                "STI 014",
            ]

            self.sfreq = 1000
            self.event_column = 11
        else:  # FreeEEG32 config
            self.channel_names = [
                "T7",
                "T8",
                "C3",
                "C4",
                "FC3",
                "FC4",
                "CP3",
                "CP4",
                "STI 014",
            ]
            self.sfreq = 512
            self.event_column = 34

        self._load()

    def _load(self):
        """Read CSV, create MNE Raw object, filter and store as .raw."""
        data = pd.read_csv(self.filename, header=None, delimiter="\t")

        if self.mentalab and self.resample:
            data = self._resample_data(data)

        eeg_data = data.iloc[:, 1:9].to_numpy().T  # shape: (n_channels, n_samples)
        eeg_data = eeg_data / 1e6  # Convert µV to V

        # Stim channel
        stim_data = np.zeros((1, eeg_data.shape[1]))
        events_column = data.iloc[:, self.event_column].to_numpy()

        last_value = 0
        for idx, value in enumerate(events_column):
            if value != 0:
                stim_data[0, idx] = value
                last_value = value
            else:
                stim_data[0, idx] = last_value

        all_data = np.vstack((eeg_data, stim_data))

        info = mne.create_info(self.channel_names, self.sfreq, self.CHANNEL_TYPES)
        raw = mne.io.RawArray(all_data, info, verbose=False)
        raw.set_montage("standard_1020", match_case=False)

        # Filtering
        raw.filter(l_freq=self.fmin, h_freq=self.fmax, verbose=False)
        raw.notch_filter(freqs=[50, 100, 150], picks="eeg", method="fir", verbose=False)

        # Bipolar derivation
        raw_bipolar = mne.set_bipolar_reference(
            raw,
            anode="C3",
            cathode="C4",
            ch_name="C3-C4",
            drop_refs=False,
            verbose=False,
        )

        self.raw = raw_bipolar

        self.events = mne.find_events(
            raw, stim_channel="STI 014", output="step", consecutive=True, verbose=False
        )

    def _resample_data(self, df):
        """Resample data from Mentablab recording"""
        values = df.iloc[:, 1:10].values  # columns 2-10
        timestamps = df.iloc[:, 10].values  # column 11
        events = df.iloc[:, 11].values  # column 12

        uniform_timestamps = np.arange(timestamps[0], timestamps[-1], 1 / self.sfreq)

        interp_values = np.empty((len(uniform_timestamps), values.shape[1]))
        for c in range(values.shape[1]):
            interp_values[:, c] = np.interp(
                uniform_timestamps, timestamps, values[:, c]
            )

        interp_events = np.zeros_like(uniform_timestamps)
        event_indices = np.where(events != 0)[0]
        for idx in event_indices:
            orig_time = timestamps[idx]
            # Find the nearest uniform grid index
            new_idx = np.abs(uniform_timestamps - orig_time).argmin()
            interp_events[new_idx] = events[idx]

        # Assemble the result DataFrame
        result_df = pd.DataFrame(
            np.hstack(
                [
                    uniform_timestamps[:, None],
                    interp_values,
                    uniform_timestamps[:, None],
                    interp_events[:, None],
                ]
            ),
            columns=["dummy"]
            + [f"val{i}" for i in range(1, 10)]
            + ["timestamp", "event"],
        )

        return result_df

    def get_events(self):
        return self.events

    def have_onoff_events(self):
        """Returns true if ON(1) or OFF(11) events are found in raw"""
        last_col = self.events[:, -1]

        mask = np.isin(last_col, list(self.EVENT_ID.values()))

        return np.any(mask)

    def _calc_onoff_duration(self):
        """Lazy estimate of the duration by counting samples between second and
        third events. Alternatively could go reading the metadata"""
        sdiff = self.events[2, 0] - self.events[1, 0]

        return int(sdiff / self.sfreq)

    def plot_timeseries(self):
        """Save the Raw plot to file"""
        fname = self.out_base + "_timeseries.png"
        browser = self.raw.plot(
            scalings={"eeg": 100e-6}, show=False, verbose=False, duration=300
        )
        browser.figure.savefig(fname, dpi=self.DPI)
        plt.close(browser.figure)

    def plot_psd(self):
        """Save Raw PSD to file"""
        fname = self.out_base + "_PSD.png"
        psd = self.raw.compute_psd(
            fmin=self.fmin * 0.8, fmax=self.fmax * 1.2, verbose=False
        )
        psd_fig = psd.plot(show=False)
        psd_fig.savefig(fname, dpi=self.DPI)
        plt.close(psd_fig)

    def _plot_epochs_timeseries(self, epochs):
        fname = self.out_base + "_epochs_timeseries.png"
        browser = epochs.plot(
            scalings={"eeg": 100e-6}, show=False, event_id=self.EVENT_ID, events=True
        )
        browser.figure.savefig(fname, dpi=self.DPI)
        plt.close(browser.figure)

    def _plot_epochs_psd(self, epochs, stitle=""):
        # epochs, output_fname, fmin=0, fmax=40,
        #         picks=None, average_psd=True, spatial_colors=True,
        #         show_plot=False, fig_size=(10, 8)):
        """
        Generates a two-subplot figure showing PSDs for "ON" and "OFF" epochs
        and saves it to a file.
        """
        fname = self.out_base + "_" + stitle + "_epochs_PSD.png"
        psd_on = epochs["ON"].compute_psd(fmin=self.fmin, fmax=self.fmax)
        psd_off = epochs["OFF"].compute_psd(fmin=self.fmin, fmax=self.fmax)

        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(10, 8), sharex=True)

        psd_on.plot(
            axes=axes[0],
            average=False,
            spatial_colors=True,
            show=False,
        )
        axes[0].set_title(f"PSD: ON {stitle} Epochs (N={len(epochs["ON"])})")

        psd_off.plot(
            axes=axes[1],
            average=False,
            spatial_colors=True,
            show=False,
        )
        axes[1].set_title(f"PSD: OFF {stitle} Epochs (N={len(epochs["OFF"])})")

        plt.tight_layout(
            rect=[0, 0.03, 1, 0.97]
        )  # Adjust rect to make space for suptitle if needed
        plt.savefig(fname, dpi=self.DPI)

        plt.close(fig)

    def plot_epochs(self):
        epochs = mne.Epochs(
            self.raw,
            events=self.events,
            tmin=0,
            tmax=self._calc_onoff_duration(),
            event_id=self.EVENT_ID,
            preload=True,
            baseline=None,
        )

        self._plot_epochs_timeseries(epochs)
        self._plot_epochs_psd(epochs)
        self._plot_epochs_psd(epochs.pick(["C3-C4"]), "C3-C4")


def main():
    cfg = Config()  # Everything is parsed and set up inside Config()

    for fname in cfg.get_matching_csv_files():
        logging.info("Opening %s", fname)

        rcsv = EEGCSVLoader(cfg, fname, 10, 100)
        rcsv.plot_timeseries()
        rcsv.plot_psd()

        if rcsv.have_onoff_events():
            rcsv.plot_epochs()


if __name__ == "__main__":
    main()
