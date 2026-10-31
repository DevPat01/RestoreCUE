# Documentation History

## Documentation V1.0 — 2026

- Preparation of the RestoreCUE technical overview document.
- Preparation of the tests and validation document.
- Creation of the English versions of both documents.
- Documentation of the communication with the console: `SHOWLIST`, `SETD`, `SAVECUE` and `CUELIST`.
- Presentation of test results obtained using a real Soundcraft Ui24R, under Windows and Linux Mint.
- Documentation of thread management, the WebSocket connection and its shutdown.

# RestoreCUE Version History

This document summarizes the main development milestones of RestoreCUE, from version V7 to version V10.

## V10 — Cue Selection and Restoration Checks

- Automatic detection of folders containing `.uicue` files within a directory and its subdirectories.
- Show folder selection by number, without manually entering its full path.
- Option to select all Cues or only some of the Cues to restore.
- Support for selections by individual numbers and ranges, for example `1-10` or `11-20`.
- Preliminary check that the Show exists on the console using `SHOWLIST`.
- Restoration is aborted if the target Show is not present; no `SETD` or `SAVECUE` commands are sent.
- Final check of the Cue names present on the console using `CUELIST`.
- Display of a summary showing the expected, found and missing Cues.
- Proper shutdown of the monitoring and periodic `ALIVE` threads before closing the socket.
- Decoding of URL-encoded Cue names to correctly display and save accented characters.
- Estimation of the restoration time and measurement of the actual elapsed time, including thread shutdown and connection closure.

## V9 — Clean Connection Shutdown

- Implementation of cooperative shutdown for the monitoring and periodic `ALIVE` threads.
- Waiting for the threads to terminate before closing the socket.
- Addition of a fallback shutdown procedure if a thread does not stop normally.
- This change aims to prevent the socket error `WinError 10053` observed when closing the connection.

## V8 — Show and Cue Verification

- Addition of a `SHOWLIST` request before sending parameters.
- Comparison of the selected Show name with the list returned by the console.
- Preventive abort if the target Show is not present.
- Addition of a final `CUELIST` check to compare the expected Cues with the names present on the console.
- Centralization of list responses received by the monitoring thread so that the main thread can process them.

## V7 — Foundation for Exhaustive Restoration

- Reading of `.uicue` export files.
- Exhaustive sending of parameters using `SETD`, while preserving their original order in the file.
- Saving of each Cue to the target Show using `SAVECUE`.
- Preservation of the distinction between parameters selected for display and the exhaustive commands used for restoration.
- Display of progress during command transmission.

---

The versions described here correspond to the main stages of development and the features added throughout testing. They are not intended to provide a detailed history of every code change.