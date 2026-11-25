# ADR-001: Motion controller is a Mesa 7i96S + 7i85S

- Date: 2026-11-25
- Status: Accepted

## Context

The mill's XHC NcUsbPod USB card only works with Mach3, so LinuxCNC needs new motion hardware. Two Mesa Ethernet cards were compared: the 7i96S and the 7i95T.

## Decision

Use a Mesa 7i96S with a 7i85S daughtercard, the same stack the owner's lathe runs. The lathe stays on its own 7i96S + 7i85S.

## Reasons

- The 7i96S has an isolated 0–10 V spindle output, which most likely connects straight to the VFD's analog speed input. The 7i95T has no analog output and would need Modbus or a PWM-to-analog converter.
- The 7i85S adds 4 encoder inputs, enough for an MPG now and linear scales or closed-loop motors later.
- One controller type across both machines: one config style, one set of spares, and boards can be swapped to find faults.

## Consequences

- 11 inputs is the tightest resource. Axis switches will probably share inputs (home and both limits on one input per axis), or a 7i84 gets added on the RS-485 port.
- The 25-pin expansion port is used by the 7i85S, so further I/O expansion goes through RS-485.

## Alternative considered

7i95T: 24 inputs, 6 encoder inputs and better ESD/RFI rejection, but no analog spindle output. Also considered for the lathe; that swap is deferred.
