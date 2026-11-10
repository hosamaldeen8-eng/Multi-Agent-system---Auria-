# Label applicator jig

Hand-cranked jig that wraps sheet labels straight onto a cylindrical jar.
The jar screws into its own lid, which is held in a rotating cup; the label
feeds from a table with a guide fence and is pressed on by a sprung roller.

- `build.py` – parametric CadQuery model (`pip install cadquery`).
  `python build.py --name B --jar-d 70 --jar-len 100 --lid-d 73 --lid-h 25`
  builds the parts for another jar; only `lid_adapter_<name>` changes per size.
- `out/*.stl` – parts to 3D print, `out/assembly_A.step` – full assembly.
- `preview.html` – interactive 3D preview (open in a browser).

Dimensions of jar A were estimated from photos and the design has not been
printed or tested yet.
