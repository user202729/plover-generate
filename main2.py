#!/bin/pypy3
## see help (main2.py -h) for more details

import sys

import local_lib

try:
	del sys.modules["lib"]
except KeyError:
	pass

from lib import *
from pathlib import Path


# parse args

default_input_files=[Path("open-dict.txt"), Path("open-dict-additional.txt")]

import argparse
parser=argparse.ArgumentParser(
		usage="Create a matched pronunciation dictionary from a pronunciation dictionary.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-a", "--append", action="store_true",
		help="Append to the output file instead of overwriting")
parser.add_argument("-i", "--input", type=Path, action="append",
		help=f"Path to input file. Can be specified multiple times. Default: {default_input_files}")
parser.add_argument("-o", "--output", type=Path,
		default=tempdir/"out",
		help="Path to output file")
parser.add_argument("--output-rules", type=Path,
		default=tempdir/"out2",
		help="Path to output file to print usages of the rules")

try:
	__IPYTHON__  # type: ignore
	args=parser.parse_args([])
except NameError:
	args=parser.parse_args()

args.input=args.input or default_input_files

## read input files

debug_print_all_matching=False

#ALL_LIMIT=10000  # most frequent
ALL_LIMIT=10**9
word_filter=lambda word: True
#word_filter=lambda word: word.lower() in {"thought", "though"}

frequency=frequency_()
pronunciation=pronunciation_(args.input[0])
for p in args.input[1:]:
	for word, pronounces in pronunciation_(p).items():
		if word not in pronunciation: pronunciation[word]=[]
		pronunciation[word]+=pronounces

print("done reading")


all_word_pronunciations: List[Tuple[
	str, # spell
	List[str]  # pronounce
	]]=list(pronunciation.items())
all_word_pronunciations=sorted(all_word_pronunciations, key=lambda y: -frequency.get(y[0], 1))
all_word_pronunciations=all_word_pronunciations[:ALL_LIMIT]
#random.shuffle(all_word_pronunciations)

all_word_pronunciations=[(word, pronunciations)
		for word, pronunciations in all_word_pronunciations
		if word_filter(word)
		]
##



if 1:
##
	used=defaultdict(list)
	with open(args.output, "a" if args.append else "w") as f, replace_stdout(f):
		for word, pronounces in all_word_pronunciations:
			print(f"++ {word}:\n")
			for pronounce in pronounces:
				result=fix_match(match(word, remove_stressed_mark(pronounce)))
				spell_, pronounce_="", ""
				for i, (s, p) in enumerate(result):
					used[s, p].append((word, pronounce))
					if i: spell_+="|"; pronounce_+="|"
					l=max(len(s), len(p))
					spell_+=s.rjust(l)
					pronounce_+=p.rjust(l)


				print(spell_)
				print(f"{pronounce_} #{pronounce}")
				print()

	with open(args.output_rules, "w") as f_:
		for (s, p), words in sorted(
				used.items(),
				key=lambda x: -len(x[1])
				):
			#if not s or not p:
			if True:
				print(f"{s}\t{p}\t{str(words)[:100]}", file=f_)
				##
