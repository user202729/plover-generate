#!/bin/pypy3

## read data. run main2.py first.

import sys

import local_lib

from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterator, Sequence
import enum
import textwrap
from collections import defaultdict


from lib import*


try:
	del sys.modules["lib_steno"]
except KeyError:
	pass

from lib_steno import *
from plover_ignore import *


# parse args

import argparse
parser=argparse.ArgumentParser(
		usage="Generate steno strokes.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-a", "--append", action="store_true",
		help="Append to the output file instead of overwriting")
parser.add_argument("-i", "--input", type=Path, action="append",
		help="Path to input file (matched pronunciation dictionary). Can be specified multiple times. "
		f"If not specified, default to {tempdir/'out'}.")
parser.add_argument("--item-limit", type=int,
		default=-1,
		help="Maximum number of items to process. Negative/default means unlimited")
parser.add_argument("-o", "--output", type=Path,
		default=tempdir/"a.json",
		help="Path to output file")
parser.add_argument("--output-errors", type=Path,
		default=tempdir/"errors.txt",
		help="Path to output file to print errors (mismatches)")

try:
	__IPYTHON__  # type: ignore
	args=parser.parse_args([])
except NameError:
	args=parser.parse_args()

args.input=args.input or [tempdir/"out"]

items=[x for p in args.input for x in matched_pronunciation_dictionary_(p)]
if args.item_limit>=0:
	items=items[:args.item_limit]
frequency=frequency_()
plover_dict=plover_dict_()
plover_dict_by_frequency=plover_dict_by_frequency_(plover_dict, frequency)
plover_reverse_dict: Dict[str, Sequence[str]]={
		word: plover_entries
		for word_frequency, word, plover_entries in plover_dict_by_frequency
		}
pronunciation: MutableMapping[str, List[str]]=defaultdict(list)
for x in items: pronunciation[spell_of_(x)].append(pronounce_of_(x))

print("done read data")

#word_filter=lambda word: not word.endswith(("ed", "s", "ing"))
# (a little too restrictive)
#word_filter=lambda word: word.lower() in {"pretty"}
word_filter=lambda word: True

##

if 1: # steno generation
	##
	errors: Set[Tuple[str, str]]=set()
	generated: MutableMapping[Strokes, List[str]]=defaultdict(list)
	generated_words: Set[str]=set()
	count=0
	out_dump=open(args.output, "w", buffering=1)
	error_dump=open(args.output_errors, "w", buffering=1)
	#out_brief_solitude=open(tempdir/"brief_solitude.txt", "w", buffering=1)
	out_brief_solitude=None

	def print_error(*args, **kwargs):
		print(*args, **kwargs)
		if error_dump: print(*args, **kwargs, file=error_dump)

	#out_dump=None
	#error_count=0
	
	def key_(x: Matches):
	# optional (set dictionary to be used by the translator, if `translate_stroke` is used)
		s=spell_of_(x)
		return (-frequency.get(s, 0), s)

	plover_briefed_words: Set[str]={plover_dict.get(x, "") for x in plover_briefs}
	for (frequency_, word), x in group_sort(items, key=key_):
		if not word_filter(word): continue
		outlines: Set[Strokes]=set()  # set of outlines generated for this word

		generated_words.add(word)

		m: Matches
		for m in x:
			count+=1
			if count%500==0:
				print("[generating steno]", count, file=sys.stderr)

			current_strokes=generate_fixed(tuple(m))

			if 0:  # print (word, pronounce) pairs that does not generate any strokes
				if not current_strokes:
					pronounce=pronounce_of_(m)
					if (word, pronounce) not in errors:
						errors.add((word, pronounce))
						print_error("error (no steno_strokes generated):", word, pronounce)
						print_matches(m)

						if 1:  # exit on (particular count of) (word-pronounce pair) errors
							if len(errors)>=100:
								raise RuntimeError()

			outlines|={*current_strokes}

		if 1:  # print words that does not generate any strokes
			if not outlines:
				print_error("error (no steno_strokes generated):", word)
				errors.add((word, ""))
				for pronounce in pronunciation.get(word, []):
					print("\t", pronounce)
				print("==")
				strokes_: str
				for strokes_ in plover_reverse_dict.get(word, []):
					print("\t", to_strokes(strokes_))

				
				if 1:  # exit on (particular count of) (unique word) errors
					if len(errors)>=100:
						raise RuntimeError()

		for outline in outlines:
			generated[outline].append(word)
			if out_dump:
				print(
					json.dumps("/".join(map(str, outline)), ensure_ascii=False)+
					":"+
					json.dumps(word, ensure_ascii=False)+
					",", file=out_dump)


		# ======== print steno mismatches with respect to Plover's dictionary

		if not word_filter(word): continue
		if word not in plover_reverse_dict: continue
		plover_entries: Sequence[str]=plover_reverse_dict[word]
		failed_strokes=[ # Plover outlines that is not ignored and cannot be guessed by the program
				plover_outline
				for plover_outline_ in plover_entries
				if plover_outline_ not in plover_ignore
				for plover_outline in [to_strokes(plover_outline_)]
				if not plover_entry_matches_generated_1(plover_outline, outlines)
				]
		#cannot_guess_any=len(failed_strokes)==len(plover_entries)
		cannot_guess_any=all(
				plover_translate(outline)!=word
				for outline in outlines)
		if cannot_guess_any and out_brief_solitude:
			print(f"{word}|", end="", file=out_brief_solitude)
		if cannot_guess_any:
			assert len(plover_entries)!=0
		#if failed_strokes:
		if cannot_guess_any and failed_strokes and word not in plover_briefed_words:
			for outline in failed_strokes:
				print(f'"{"/".join(x.raw_str() for x in outline)}", # {"!! " if cannot_guess_any else ""}{outline}: {word} -- {pronunciation.get(word)}',
						file=error_dump
						)
			print(
					'\n'.join(
						f"    # {line}"
						for line in textwrap.wrap(
							f"generated: " +
							', '.join('/'.join(map(str, outline)) for outline in outlines)
							)
						)
					,
					file=error_dump)
