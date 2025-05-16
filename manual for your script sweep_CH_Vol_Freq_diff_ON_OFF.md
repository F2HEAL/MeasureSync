Here's a **brief manual** for your script `sweep_CH_Vol_Freq_diff_ON_OFF.py`, including:

* What it does

* Configuration overview

* Marker definitions and their meaning

---

## **🧠 Script Purpose**

This Python script synchronizes **EEG data recording via BrainFlow** with **VBS (vibrotactile brain stimulator haptic) device control**. It supports:

* Multiple stimulation frequencies, volumes, and channels

* EEG recording with event markers

* Recording of 1 or 2 **baseline EEG periods:**  
  *  **If  VBS is powered OFF (in a separate file)**  
  * **Prior to 1st stimulation**

* Automatic detection of VBS power-on via serial connection

---

## **📁 Required Files**

* A **measurement YAML file** (via `-m`) defining stim parameters

* A **device YAML file** (via `-d`) specifying board and serial settings

---

## **⚙️ Key Features**

* Uses BrainFlow and a Mentalab Explore or Freeeeg32 (or other board)

* Automatically logs EEG baseline while waiting for VBS to be powered ON

* Inserts precise **event markers** into EEG stream

* Writes EEG data to `.csv` files for each stim combination

* Records metadata to a `.txt` file

---

## **🧭 Execution Example**

bash  
`python sweep_CH_Vol_Freq_diff_ON_OFF.py -m config_measure.yaml -d config_device.yaml -v`

---

## **🏷️ Markers Used in EEG Stream**

| File | Marker ID | Purpose / Meaning |
| :---: | :---: | ----- |
| **1** | **3** | Start of EEG baseline  part I EEG if/with VBS powered OFF |
| **1** | **33** | Start of EEG baseline  part II after VBS has been powered ON (end of baseline part I) |
| **2** | **333** | Start of EEG baseline  part II bis pre-stimulation EEG with VBS ON (before first stim event) |
| **2** | **1** | VBS stimulation ON |
| **2** | **11** | VBS stimulation OFF |

---

## **🔄 Measurement Flow**

1. **Start EEG stream**

2. Check if VBS is connected

   * If not: record EEG baseline and insert **marker 3**

   * When connected: insert **marker 33**

3. Wait for `Pre-start_EEG_measurement` duration

4. For each combination of:

   * Channel (`C`)

   * Frequency (`F`)

   * Volume (`V`)  
      it:

   * Sets VBS parameters

   * Inserts **marker 333**  
   * Wait for `Pre-start_EEG_measurement` duration

   * Loops through `Measurements.Number`:

     * Sends **marker 1**, starts VBS stimulation

     * Sends **marker 11**, stops VBS stimulation

5. EEG stream stops, metadata is saved

---

## **🗂️ Recorded Files**

* `File 1: Recordings/[timestamp]_...baseline_with_VBS_powered_OFF_on_persons_head_YES_NO.csv`  
   → Baseline EEG when VBS is OFF\>ON  
* `File 2: Recordings/[timestamp]_..._c[chan]_f[freq]_v[vol].csv`  
   → One file per stimulation condition

* `File 3: Recordings/[timestamp]_metadata.txt`  
   → Contains YAML config contents \+ notes \+ baseline file used

---

## **💡 Tips**

* You can modify `marker()` calls to include condition IDs (e.g., `100 + i`) if needed

* BLE stability is ensured by keeping EEG streaming active throughout

* The script is compatible with synthetic boards for testing (set `Id: SYNTHETIC_BOARD` in YAML)

### **🔄 Optional BLE Keep-Alive Thread (Function Overview)**

The script includes an optional background thread (`keep_ble_alive`) that continuously polls EEG data using `board_shim.get_board_data()` at regular intervals. This helps **prevent BLE disconnection** from some BrainFlow boards (e.g., Mentalab Explore) that may drop the Bluetooth link when idle.

The thread runs **only if** the following is set in the device YAML:

yaml

  `Keep_ble_alive: true`

* It starts automatically after EEG streaming begins.

* It is lightweight and non-blocking (`daemon=True`).

* It safely exits if the board disconnects or the session ends.

**Use this option if you're working with BLE-based devices that tend to disconnect between stimulation blocks or during baseline periods.**

