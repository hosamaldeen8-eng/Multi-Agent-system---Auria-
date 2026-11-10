# Label applicator jig

Hand-cranked jig that wraps sheet labels straight onto a cylindrical jar.
The jar screws into its own lid, which is held in a rotating cup. A clamp bar
hinged on the cup pins the label's leading edge square to the jar and turns
with it; a fixed hinged arm rests a rubber squeegee blade on top of the jar to
press the label down and push the air out as the crank is turned.

- `build.py` – parametric CadQuery model (`pip install cadquery`).
  `python build.py --name B --jar-d 70 --jar-len 100 --lid-d 73 --lid-h 25`
  builds the parts for another jar; only `lid_adapter_<name>` and `clamp_<name>` change per size.
- `out/*.stl` – parts to 3D print, `out/assembly_A.step` – full assembly.
- `preview.html` – interactive 3D preview (open in a browser).

Dimensions of jar A were estimated from photos and the design has not been
printed or tested yet.
