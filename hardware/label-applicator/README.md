# Label applicator jig

Hand-cranked jig that wraps sheet labels straight onto a cylindrical jar.
The jar screws into its own lid, which is held in a rotating cup. A ruler
seats on a tapered rail on the cup, parallel to the jar axis, with a side stop
square to it; the label is pushed into that corner so it starts square, and
the ruler turns with the jar. A fixed hinged arm rests a rubber squeegee blade
on top of the jar to press the label down as the crank is turned. The ruler
lifts off before the end of a full-wrap label comes round.

- `build.py` – parametric CadQuery model (`pip install cadquery`).
  `python build.py --name B --jar-d 70 --jar-len 100 --lid-d 73 --lid-h 25`
  builds the parts for another jar; only `lid_adapter_<name>` and `ruler_<name>` change per size.
- `out/*.stl` – parts to 3D print, `out/assembly_A.step` – full assembly.
- `preview.html` – interactive 3D preview (open in a browser).
- `make_pdf.py` – builds `label-applicator-guide-<name>.pdf`, the Arabic build
  and assembly guide (needs Node with Playwright).

Dimensions of jar A were estimated from photos and the design has not been
printed or tested yet.

## Simple wooden version

`simple/build_simple.py` models a no-printer build for closed jars: the jar
goes in with its lid on, held between a wooden head with a stepped socket (fits
both the 101 mm and the 90 mm lid) and a sprung tail pad. An aluminium flat bar
on the head is the ruler, and a hinged arm carries the squeegee rubber. The
script checks both jar sizes and writes `simple/preview.html` with the cut
list and shopping list (`--size small` draws the small jar).
