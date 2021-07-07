#!/bin/pypy3

import re
import local_lib
from lib import*
from lib_steno import*
import itertools

default_input_files=[tempdir/"out"]

import argparse
parser=argparse.ArgumentParser(
		usage="Lookup pronunciation according to spelling.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-i", "--input", type=Path, action="append",
		help="Path to input file (matched pronunciation dictionary). Can be specified multiple times. "
		f"If not specified, default to {default_input_files}.")
parser.add_argument("query",
		help="Regular expression to match the spelling.")
args=parser.parse_args()

args.input=args.input or default_input_files

items=[x for p in args.input for x in matched_pronunciation_dictionary_(p)]
m: Matches
d: MutableMapping[str, List[str]]=defaultdict(list)
for m in items:
	word=spell_of_(m)
	spell_pos_to_match_pos: Optional[Dict[int, int]]=None
	for match_ in re.finditer(args.query, word):
		if spell_pos_to_match_pos is None:
			spell_pos_to_match_pos={
					v: i for i, v in enumerate(itertools.accumulate(
						[0]+[len(x.spell) for x in m]
						))
					}

		start=spell_pos_to_match_pos.get(match_.start())
		end=spell_pos_to_match_pos.get(match_.end())
		if start is not None and end is not None:
			d[pronounce_of_(m[start:end])].append(word)

max_pronounce_len=max(len(pronounce) for pronounce in d.items())
for pronounce, words in sorted(d.items(), key=lambda x: len(x[1]), reverse=True):
	print(f"{pronounce:{max_pronounce_len}}  {len(words):5}  {str(words)[:100]}")
