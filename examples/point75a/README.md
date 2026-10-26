# Point75A crossover, version 12

This example transcribes the 25 R/C/L symbols in Troels Gravesen's complete three-way crossover, Figure 31 on PDF page 11 of [The Point75 / Going three-way](http://www.troelsgravesen.dk/download/Point75A%26B.pdf). The source drawing uses values rather than component reference names; `R1`–`R8`, `C1`–`C9` and `L1`–`L8` are identifiers assigned for this example.

The three rows preserve the published tweeter, midrange and woofer networks. Their component counts are 10, 12 and 3: 8 resistors, 9 capacitors and 8 inductors overall. All 25 nominal values are retained, including the 26.8 µF capacitor. The `<0R2` text beside the woofer coils describes coil resistance limits, rather than additional resistor symbols.

Four clearly separate test fixtures make the example runnable: a 1 V source `U1` and three 8 Ω load resistors `R_TW`, `R_MID`, `R_WOOF`. The loads represent the three external loudspeakers as resistances. The resulting file has 29 components. The published drawing's acoustic responses cannot be reproduced with these resistive loads and ideal inductors.

`IN`, `TW`, `MID` and `WOOF` are external electrical test points. Voltage references use each lower filtered path against the common upper return rail. The source drawing's driver polarity labels should be consulted for physical speaker wiring; this example evaluates electrical filter responses, without an acoustic summation model.

The original PDF and its images are linked for comparison and are not redistributed with this example. The JSON contains a transcription of circuit connections and component values, with a new native layout and explicitly identified test fixtures.
