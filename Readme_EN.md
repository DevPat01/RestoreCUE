[Version française](README.md)
# RestoreCUE

## Cue Restoration Tool for Soundcraft, tested on Ui24R

## Compatibility

**Console:** Soundcraft Ui24R

**Public reference firmware:**  
Ui24R Firmware v3.5.8328

**Computer operating systems:**
- Windows 10 / 11
- Linux (particularly Linux Mint)

**Communication:**  
WebSocket / Socket.IO protocol

Restoration tests were performed on a real Ui24R console.

**Author and developer:** Patrick ARNAUD  
**Version:** V10  
**Year:** 2026

---

## Overview

RestoreCUE is an independent Python-based software application designed to rebuild and restore Cues on Soundcraft Ui24R consoles using individual `.uicue` export files.

These files correspond to Cues exported from a Show and contain the settings required to rebuild them.

The project was created to meet a practical need: to recover and rebuild the Cues of a Show from backup files stored on a USB drive, without having to recreate them manually.

The USB drive containing the backup must be connected to the computer so that the program can access the exported files.

RestoreCUE communicates directly with the console over WebSocket using the commands provided by its control interface.

## Features

- Connection to the console using its IP address.
- Automatic search for folders containing `.uicue` files, including on a USB drive.
- Selection of the Show folder by number, without manually entering its path.
- Display of the available Cue list.
- Restoration of all Cues or individual Cue selection.
- Selection by number ranges (for example: `1-10` or `11-20`).
- Exhaustive reading of commands from `.uicue` files.
- Sending of all parameters in their original order.
- Preliminary check that the Show exists on the console.
- Saving of each Cue to the target Show.
- Final check that the Cues are present on the console.
- Progress bar and restoration time estimate.
- Connection management and clean thread shutdown.

## General Operation

To restore a Show, the program:

1. Searches for folders containing `.uicue` files.
2. Allows the user to select the folder corresponding to the Show.
3. Displays the Cue list and allows a selection to be made.
4. Checks that the Show exists on the console using `SHOWLIST`.
5. Sends each Cue's parameters using `SETD` commands, preserving their original order.
6. Saves each Cue to the target Show using `SAVECUE`.
7. Checks the names of the Cues present on the console using `CUELIST`.

> [!WARNING]
> RestoreCUE never uses the `LOADCUE` command.
>
> The `SETD` commands modify the active mix settings during reconstruction. It is therefore essential to make a backup beforehand and to test the program on a test Show first.
>
> The target Show must already exist on the console. If the requested Show is not present, restoration is aborted before any modification commands are sent.

## Installation

RestoreCUE runs on:
- Windows 10 / 11
- Linux (particularly Linux Mint)

> [!NOTE]
> Python 3 must be installed.
>
> The program uses only Python's standard libraries and does not require a graphical user interface.

## Usage

1. Connect the computer to the Ui24R network, preferably using an Ethernet cable (RJ45).
2. Run the program using the command corresponding to the operating system:
   - Windows: `python V10RestoreCUE.py`
   - Linux Mint: `python3 V10RestoreCUE.py`
3. Check the console's IP address.
4. Select the Show folder.
5. Review the available Cues.
6. Press `E` to start the restoration.
7. Select the Cues to restore, or press Enter to restore them all.

A final summary shows the number of expected, found and missing Cues.

> [!TIP]
> A Show containing many Cues can be restored in several batches.
>
> For example: select `1-10`, then `11-20`, and so on.

## Documentation

Detailed documents are available in the `docs` folder:

- [Technical Overview](docs/Functionality.md)
- [Tests and Validation](docs/Tests_and_Validation.md)

## Tests Performed

The program has been tested on a real Soundcraft Ui24R console connected to a computer running Windows and Linux Mint.

All tests were performed using a wired Ethernet connection (RJ45). Wi-Fi operation has not been validated through testing.

Examples of tests performed:

- Full restoration of 41 Cues: 41 found.
- Partial restoration of 10 Cues: 10 found.
- Restoration of 2 Cues: 2 found.
- Verification that the Show exists before restoration.
- Final verification of the Cue list.
- Verification of clean thread shutdown and socket closure.

> [!CAUTION]
> The `CUELIST` check confirms that the expected Cue names are present on the console.
>
> It does not individually verify the integrity of all restored parameter values. An additional check on the console is still recommended.

## Disclaimer

> [!WARNING]
> RestoreCUE is an independent project and is not affiliated with, endorsed by, or sponsored by Soundcraft or Harman International.
>
> Soundcraft and Ui24R are trademarks of their respective owners.
>
> The software is provided without warranty. Users remain responsible for their backups and for any operations performed on the console.


## License and Copyright

RestoreCUE V10 is distributed under the MIT License.

Copyright (c) 2026 Patrick ARNAUD.

You are free to use, copy, modify, and redistribute this software, including for commercial purposes, provided that the copyright notice and license text are retained in all copies or substantial portions of the software.

See the [LICENSE](LICENSE) file for the full license text.

## e-Soleau Deposit – INPI

The RestoreCUE V10 project and its associated documentation have been deposited with the French National Institute of Industrial Property (INPI) through its e-Soleau service, providing dated evidence of their existence and contents.

Deposit date: [deposit date]