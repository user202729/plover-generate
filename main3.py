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

default_input_files=[tempdir/"out"]

import argparse
parser=argparse.ArgumentParser(
		usage="Generate steno strokes.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-a", "--append", action="store_true",
		help="Append to the output file instead of overwriting")
parser.add_argument("-i", "--input", type=Path, action="append",
		help="Path to input file (matched pronunciation dictionary). Can be specified multiple times. "
		f"If not specified, default to {default_input_files}.")
parser.add_argument("--item-limit", type=int,
		default=-1,
		help="Maximum number of items to process. Negative/default means unlimited")
parser.add_argument("-o", "--output", type=Path,
		default=tempdir/"a.json",
		help="Path to output file")
parser.add_argument("--output-errors", type=Path,
		default=tempdir/"errors.txt",
		help="Path to output file to print errors (mismatches)")
parser.add_argument("--no-output-errors", action="store_true",
		help="Do not print errors. See also --output-errors")
parser.add_argument("--raw-steno", action="store_true",
		help="Print raw steno instead of pseudosteno")
parser.add_argument("--include-briefs", action="store_true",
		help="Include briefs in the output file")
parser.add_argument("--disambiguation-stroke", type=Stroke, default=Stroke(),
		help=f"Stroke to disambiguate conflicts")
parser.add_argument("--last-entry", default='"WUZ/WUZ": ""',
		help=f"Last entry. "
		"If empty, the surrounding {...} are not generated and the output is not a valid JSON file. "
		"This is not checked to be a valid JSON or stroke."
		)


try:
	__IPYTHON__  # type: ignore
	args=parser.parse_args([])
except NameError:
	args=parser.parse_args()

args.input=args.input or default_input_files

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

def outline_to_str(outline: Strokes, raw_steno: bool=args.raw_steno)->str:
	return "/".join(
			x.raw_str() if raw_steno else str(x)
			for x in outline)

def have_ignore_part(outline: str)->bool:
	parts: List[str]=outline.split("/")
	return any(
			"/".join(parts[l:r]) in plover_ignore
			for r in range(len(parts)+1)
			for l in range(r)
			)

##

if 1: # steno generation
	##
	errors: Set[Tuple[str, str]]=set()
	generated: MutableMapping[Strokes, List[str]]=defaultdict(list)

	generated_words: Set[str]=set()
	count=0
	out_dump=open(args.output, "w", buffering=1)
	error_dump=None if args.no_output_errors else open(args.output_errors, "w", buffering=1)

	if out_dump and args.last_entry:
		print("{", file=out_dump)

	def append_generated(outline: Strokes, word: str)->None:
		generated[outline].append(word)
		if out_dump:
			print(
				json.dumps(outline_to_str(
					outline + (args.disambiguation_stroke,)*(len(generated[outline])-1)
					if args.disambiguation_stroke else outline
					), ensure_ascii=False)+
				":"+
				json.dumps(word, ensure_ascii=False)+
				",", file=out_dump)

	def print_error(*args, **kwargs):
		print(*args, **kwargs)
		if error_dump: print(*args, **kwargs, file=error_dump)

	if args.include_briefs:
		for x in plover_briefs|plover_ortho_briefs:
			append_generated(to_strokes(x), plover_dict[x])

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
			append_generated(outline, word)


		# ======== print steno mismatches with respect to Plover's dictionary

		if word not in plover_reverse_dict: continue
		if error_dump is None: continue
		plover_entries: Sequence[str]=plover_reverse_dict[word]
		failed_strokes: List[Strokes]=[ # Plover outlines that is not ignored and cannot be guessed by the program
				plover_outline
				for plover_outline_ in plover_entries
				#if plover_outline_ not in plover_ignore
				if not have_ignore_part(plover_outline_)
				for plover_outline in [to_strokes(plover_outline_)]
				if not plover_entry_matches_generated_1(plover_outline, outlines)
				]
		#cannot_guess_any=len(failed_strokes)==len(plover_entries)
		cannot_guess_any=all(
				plover_translate(outline)!=word
				for outline in outlines)
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
							', '.join(outline_to_str(outline) for outline in outlines)
							)
						)
					,
					file=error_dump)

	if out_dump and args.last_entry:
		print(args.last_entry+"\n}", file=out_dump)
