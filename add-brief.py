# Python dictionary.
# To use: install plover-python-dictionary plugin, copy this file to Plover's configuration folder
#    (do not change the filename, it's hard coded in the script)
#    then add this file as a dictionary in Plover.
#  Also install plover-run-shell plugin and create an empty JSON dictionary in
#    Plover's configuration folder, named `briefs.json`.
# To mark a word: (only 1-stroke words are supported)
#  Stroke the word, then stroke the `mark_stroke` twice.

mark_stroke="PHO*EURBG"  # mark + oi*

import sys
if len(sys.argv)==5 and sys.argv[1]=="--add":
	import json
	from pathlib import Path
	briefs_path_: Path=Path(sys.argv[2])
	data=json.loads(briefs_path_.read_text())
	data[sys.argv[3]]=sys.argv[4]
	briefs_path_.write_text(json.dumps(data, ensure_ascii=False, indent=0))
	sys.exit()


from typing import Tuple, Dict
from plover.oslayer.config import CONFIG_DIR  # type: ignore
from pathlib import Path
import json
import shlex

LONGEST_KEY=3

main_dict: Dict[str, str]=json.loads((Path(CONFIG_DIR)/"main.json").read_text())
script_path: Path=Path(CONFIG_DIR)/"add-brief.py"
briefs_path: Path=Path(CONFIG_DIR)/"briefs.json"


def escape_translation(translation: str)->str:
	return translation.translate({
		ord("{"): r"\{",
		ord("}"): r"\}",
		})

def lookup(strokes: Tuple[str, ...])->str:
	if len(strokes)>=2 and all(x==mark_stroke for x in strokes[1:]):
		stroke=strokes[0]
		translation=main_dict[stroke]
		if len(strokes)==2:
			return f"[:: '{stroke}' -> '{escape_translation(translation)}' ?]"
		else:
			assert len(strokes)==3
			return (
					"{plover:shell:python " +
					escape_translation(
						' '.join(shlex.quote(x) for x in [
							str(script_path), "--add", str(briefs_path), stroke, translation])
						) +
					"}" +
					"{plover:set_config}" + translation
					)
	raise KeyError
