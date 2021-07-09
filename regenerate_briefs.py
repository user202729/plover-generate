#!/bin/python
"""
Filter out the unnecessary entries (derivative form of an existing brief) from plover_briefs.
"""
from plover_ignore import*
from lib_steno import*
plover_dict={
		to_strokes(a): b
		for a, b in plover_dict_().items()}
outlines: List[Strokes]=[to_strokes(outline_) for outline_ in plover_briefs]

suffix_lookup: Dict[Stroke, str]={}
for suffix in map(Stroke, "-G -S -Z -D".split()):
	t: str=plover_dict[suffix,]
	match_=re.fullmatch("{\^(.*)}", t)
	assert match_ is not None
	suffix_lookup[suffix]=match_[1]

import plover  # type: ignore
from plover.registry import registry                        # type: ignore
from plover import system                                   # type: ignore

registry.update()
system.setup("English Stenotype")

for outline in outlines:
	word: str=plover_dict[outline]
	keep=True
	for suffix_stroke, suffix_str in suffix_lookup.items():
		candidate: Optional[Strokes]=None
		if suffix_stroke==outline[-1]:
			candidate=outline[:-1]
		elif suffix_stroke in outline[-1]:
			candidate=outline[:-1]+(outline[-1]-suffix_stroke,)
		if candidate is None: continue
		if candidate not in plover_dict: continue
		if plover.orthography.add_suffix(
				plover_dict[candidate],
				suffix_str
				)!=word:
			continue
		keep=False
		break

	if keep:
		content=f'"{"/".join(x.raw_str() for x in outline)}",'
		print(f'{content:25} # {word}')

if isinstance(plover_briefs, set):
	print("Note: plover_briefs is unordered.", file=sys.stderr)
