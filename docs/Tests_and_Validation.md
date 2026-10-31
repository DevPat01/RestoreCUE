# RestoreCUE Tests and Validation

## 1. Test Environment and Scope

The reported tests were performed using a real Soundcraft Ui24R console connected to a computer. The software was also used under Windows and Linux Mint.

The `.uicue` files used during testing contained 2,356 commands per Cue.

The delay settings used during the most recent tests were:

```python
DELAY_BETWEEN_PARAMS = 0.001
DELAY_AFTER_CUE = 0.3
```

The results below are tests performed under the described configuration. They do not constitute certification of compatibility with all firmware versions, network configurations or Shows.

All RestoreCUE validation tests were performed using a wired Ethernet connection (RJ45) between the computer and the Soundcraft Ui24R console.

The recorded execution times apply exclusively to this configuration. No comparative measurements or performance validation using Wi-Fi have been carried out.

## 2. Preliminary Show Verification — `SHOWLIST`

A test was performed using a target Show named `TestPat` that was not present in the console's Show list.

Observed result:

- the program received the list of Shows;
- `TestPat` was reported as absent;
- the restoration was interrupted;
- no `SETD` or `SAVECUE` commands were sent;
- the threads were stopped and the socket was closed cleanly.

A separate test confirmed that `TestPat` was present in `SHOWLIST` and allowed the restoration to proceed.

## 3. Restorations Performed

| Test | Cues selected | Cues found | Missing Cues | Estimated time | Actual time |
| --- | --: | --: | --: | --: | --: |
| Single Cue restoration | 1 | 1 | 0 | 4 s | 5 s |
| Two Cue restoration | 2 | 2 | 0 | 7 s | 9 s |
| Partial restoration | 10 | 10 | 0 | 44 s | 46 s |
| Full restoration — test 1 | 41 | 41 | 0 | 2 min 17 s | 3 min 01 s |
| Full restoration — test 2 | 41 | 41 | 0 | 3 min 00 s | 3 min 08 s |

### Single Cue Restoration

A Cue named `CUE2` was rebuilt from 2,356 commands. The final check found the Cue in the Show list.

### Partial Restoration of 10 Cues

Ten Cues were selected from a Show containing 41 Cues. The final check found all ten expected Cues; the Show still contained a total of 41 Cues.

### Full Restoration of 41 Cues

Two full restoration runs were reported. In both cases, all 41 expected Cues were found, with no missing Cues reported.

## 4. Final Verification — `CUELIST`

The `CUELIST` response made it possible to compare the names of the selected Cues with those returned by the console.

The reported results were:

- 1 expected Cue: 1 found;
- 2 expected Cues: 2 found;
- 10 expected Cues: 10 found;
- 41 expected Cues: 41 found in each of two tests.

In partial restoration tests, the total number of Cues returned by the console was greater than or equal to the number of selected Cues. This is normal when the Show already contains other Cues.

**Limitation:** the `CUELIST` response confirms the presence of Cue names. On its own, it cannot verify all 2,356 parameter values in each Cue.

## 5. Thread Shutdown and Socket Closure

Following the implementation of cooperative shutdown:

- the monitoring thread indicated that a shutdown had been requested and that reading had finished;
- the monitoring and `ALIVE` threads were stopped before the socket was closed;
- the program reported that the socket had been closed cleanly;
- no further `WinError 10053` messages were reported in the successful tests presented here.

The shutdown times measured during the reported tests were approximately 0.01 to 0.04 seconds.

## 6. Observations on Execution Times

Estimated times were adjusted throughout the testing process. For smaller restorations, the difference between the estimate and the actual duration was a few seconds. In the second test involving 41 Cues, the estimated time was 3 minutes, compared with an actual duration of 3 minutes and 8 seconds.

These measurements are indicative only. It is preferable to retain a margin in the estimate rather than treating the observed durations as guaranteed.

## 7. Items Still to Be Verified

The tests described confirm the following:

- connection to the console and reception of list responses;
- preliminary verification that the target Show is present;
- sending commands and saving Cues;
- presence of the expected Cue names in `CUELIST` after restoration;
- clean thread shutdown and socket closure.

However, these tests do not by themselves demonstrate that every parameter value in every Cue has been saved without error. For a complete content validation, it is still recommended to recall Cues on the console and check their settings, or to compare a detailed readout of their state when such a method is available.