#!/bin/pypy3

## read data. run main2.py first.

from time import time
start_time=time()

import sys

import local_lib

from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterator, Sequence
import enum
import textwrap
from collections import defaultdict


from lib import*

warn_if_not_optimization()

try:
	del sys.modules["lib_steno"]
except KeyError:
	pass

from lib_steno import *
from plover_ignore import *


# parse args

default_input_files=[tempdir/"out"]
generate_equivalent="--raw-steno --include-briefs --no-output-errors --disambiguation-stroke=R-RPB"

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
parser.add_argument("--print-push", action="store_true",
		help=f"Whether to print cases where candidate words are not ordered by frequency.")
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
parser.add_argument("--word-filter",
		help=f"If not empty, list of comma-separated words to filter the output."
		)
parser.add_argument("--generate", action="store_true",
		help=f"Preset for generating a dictionary. "
		f"Equivalent to appending '{generate_equivalent}' to the command-line."
		)


try:
	__IPYTHON__  # type: ignore
	args=parser.parse_args([])
except NameError:
	args=parser.parse_args()

if args.generate:
	args=parser.parse_args(sys.argv[1:]+generate_equivalent.split())

args.input=args.input or default_input_files

items=[x for p in args.input for x in matched_pronunciation_dictionary_(p)]  # spelling are in lowercase
if args.item_limit>=0:
	items=items[:args.item_limit]

frequency=frequency_()
frequency_items=[
		(word_lower, [*items_])
		for word_lower, items_ in group_sort(frequency.items(), key=lambda x: x[0].lower())]
frequency_lowercase: Dict[str, float]={
		word_lower: sum(x[1] for x in items_) for word_lower, items_ in frequency_items}
casereverse: Dict[str, List[str]]={ #only consist of words in the frequency file
		word_lower: [x[0] for x in items_] for word_lower, items_ in frequency_items}

base_form_lower: Dict[str, str]={
		word.lower(): base.lower()
		for word, base in base_form_().items()
		}

plover_dict=plover_dict_()
plover_dict_by_frequency=plover_dict_by_frequency_(plover_dict, frequency)
plover_reverse_dict: Dict[str, Sequence[str]]={
		word: plover_entries
		for word_frequency, word, plover_entries in plover_dict_by_frequency
		}
pronunciation: MutableMapping[str, List[str]]=defaultdict(list)  # spelling are in lowercase
for x in items: pronunciation[spell_of_(x)].append(pronounce_of_(x))

print("done read data")

#word_filter=lambda word: not word.endswith(("ed", "s", "ing"))
# (a little too restrictive)
#word_filter=lambda word: word.lower() in {"pretty"}
word_filter=lambda word: True
if args.word_filter:
	keep_words: Set[str]={*args.word_filter.lower().split(",")}
	word_filter=lambda word: word in keep_words


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

errors: Set[Tuple[str, str]]=set()
generated: MutableMapping[Strokes, List[str]]=defaultdict(list)
@dataclass
class Outline_:
	outline: Strokes
	frozen: bool
outlines_for: MutableMapping[str, List[Outline_]]=defaultdict(list)

def direct_strokes(word: str, frozen: bool=None)->List[Outline_]:
	# number of possible shortest strokes to write this word that doesn't use disambiguation_stroke
	outlines=[
			outline
			for outline in outlines_for[word]
			if generated[outline.outline][0]==word and (frozen is None or outline.frozen==frozen)
			]
	if not outlines: return []
	length=min(len(x.outline) for x in outlines)
	return [x for x in outlines if len(x.outline)==length]

count=0
out_dump=open(args.output, "w", buffering=1)
error_dump=None if args.no_output_errors else open(args.output_errors, "w", buffering=1)

def print_error(*args, **kwargs):
	print(*args, **kwargs)
	if error_dump: print(*args, **kwargs, file=error_dump)

try:

	briefed_words_lower: Set[str]=set()
	if args.include_briefs:
		for x in plover_briefs|plover_ortho_briefs:
			word=plover_dict[x]
			briefed_words_lower.add(word.lower())
			outline=to_strokes(x)
			outlines_for[word].append(Outline_(outline, frozen=True))
			generated[outline].append(word)

	#out_dump=None
	#error_count=0
	
	def key_(x: Matches)->Tuple[float, float, str]:
		s=spell_of_(x)
		return (
				-frequency_lowercase.get(s, 0),
				-frequency_lowercase.get(base_form_lower.get(s, ""), 0),
				s)

	plover_briefed_words: Set[str]={plover_dict.get(x, "") for x in plover_briefs}
	for (frequency__, frequency_base_, word_lower), x in group_sort(items, key=key_):
		if not word_filter(word_lower): continue
		outlines: Set[Strokes]=set()  # set of outlines generated for this word

		m: Matches
		for m in x:
			count+=1
			if count%500==0:
				print("[generating steno]", count, file=sys.stderr)

			current_strokes=generate_fixed(tuple(m))

			if 0:  # print (word, pronounce) pairs that does not generate any strokes
				if not current_strokes:
					pronounce=pronounce_of_(m)
					if (word_lower, pronounce) not in errors:
						errors.add((word_lower, pronounce))
						print_error("error (no steno_strokes generated):", word_lower, pronounce)
						print_matches(m)

			outlines|={*current_strokes}

		if 1:  # print words that does not generate any strokes
			if not outlines:
				print_error("error (no steno_strokes generated):", word_lower)
				errors.add((word_lower, ""))
				for pronounce in pronunciation.get(word_lower, []):
					print("\t", pronounce)
				print("==")
				strokes_: str
				for strokes_ in plover_reverse_dict.get(word_lower, []):
					print("\t", to_strokes(strokes_))

		if word_lower in briefed_words_lower:
			for outline in [*outlines]:
				outline_=outline_to_str(outline, raw_steno=True)
				if outline_ in plover_ignore and plover_dict[outline_].lower()==word_lower:
					print_error(f"Redundant brief {outline} for {word_lower}")
					outlines.remove(outline)

		for word in casereverse.get(word_lower, [word_lower]):
			for outline in outlines:
				assert all(x.outline!=outline for x in outlines_for[word]), (word, outline, outlines_for[word])
				outlines_for[word].append(Outline_(outline, frozen=False))
				generated[outline].append(word)

			# rearrange words
			# use something similar to the maximum matching algorithm, but only consider one retraction
			if not direct_strokes(word):
				for x in sorted(outlines_for[word], key=lambda x: len(x.outline)):
					outline=x.outline
					other_word: str=generated[outline][0]
					d=direct_strokes(other_word)
					d0=[d_ for d_ in d if d_.outline==outline]
					assert len(d0)<=1, (word, outline)
					if d0 and d0[0].frozen:
						# cannot move other_word
						continue
					if (
							# outline is not a direct stroke of other_word
							# (it's longer than other_word's shortest stroke)
							not d0

							# there's another direct stroke
							or len(d)>=2
							):
						# use (outline) for this word
						# preserve the order of other words
						assert generated[outline][-1]==word
						generated[outline]=[word]+generated[outline][:-1]
						if args.print_push:
							print(f"{word} push {other_word} from {outline} to " +
							str([d0.outline for d0 in direct_strokes(other_word)])
							)
						break


		# ======== print steno mismatches with respect to Plover's dictionary

		if error_dump is None: continue
		plover_entries: Sequence[str]=[
				outline_
				for word in casereverse.get(word_lower, [word_lower])
				for outline_ in plover_reverse_dict.get(word, ())
				]
		if not plover_entries: continue
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
				plover_translate(outline)!=word_lower
				for outline in outlines)
		if cannot_guess_any:
			assert len(plover_entries)!=0
		#if failed_strokes:
		if cannot_guess_any and failed_strokes and word_lower not in plover_briefed_words:
			for outline in failed_strokes:
				print(f'"{"/".join(x.raw_str() for x in outline)}", # {"!! " if cannot_guess_any else ""}{outline}: {word_lower} -- {pronunciation.get(word_lower)}',
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

except KeyboardInterrupt:
	print("KeyboardInterrupt received, stop generating dictionary")

print("Writing to output file...")
try:
	if out_dump and args.last_entry:
		print("{", file=out_dump)

	for outline, words in generated.items():
		for i, word in enumerate(words):
			print(
				json.dumps(outline_to_str(
					outline +
					((args.disambiguation_stroke,)*i if args.disambiguation_stroke else ())
					), ensure_ascii=False)+
				":"+
				json.dumps(word, ensure_ascii=False)+
				",", file=out_dump)

finally:
	if out_dump and args.last_entry:
		print(args.last_entry+"\n}", file=out_dump)
	print(f"Done. (total time = {time()-start_time:.3f} seconds)")
