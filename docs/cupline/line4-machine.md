# Line 4 cup former: electrical interface (FICTIONAL)

> Fictional test corpus for eval scenario conv_cup_line_sensor_grounded (ARCH-20260930-094). It describes no real machine.

- Controller PCB: CF-IO8.
- Sensor supply rail: 24 VDC, plus or minus 5% at the PCB terminals (22.8 V minimum, 25.2 V maximum), up to 150 mA per sensor channel.
- Digital inputs DI0 to DI7 are designed for NPN open-collector sensor outputs: an NPN output switching the input to 0 V reads as ON. They are compatible with the Keyence LV-N11N.
- The registration-mark sensor connects to input DI3.
- Line speed: 150 cups per minute maximum, one registration mark per cup.
- Commissioning pass thresholds:
  - Supply voltage measured at the sensor head, powered: pass if between 21.6 V and 26.4 V (24 V plus or minus 10%).
  - Output switching at maximum line speed: pass if DI3 counts 150 of 150 marks in 60 seconds. Any missed mark fails.
