#!/bin/python

from time import time
start_time=time()

from pathlib import Path
from lib import *
import json
import argparse
parser=argparse.ArgumentParser(usage="""\
Determine word boundary conflicts.

It's usually not necessary to use this script for generated dictionaries.
""")
parser.add_argument("dictionary", type=Path, help="Path to JSON dictionary.")
parser.add_argument("ngrams_file", type=Path, nargs="?", default=Path("bigram-frequency.json"),
		help="Path to n-grams file. Must be a JSON file that contains an iterable")
parser.add_argument("--disambiguation-stroke", type=str, default="R-RPB",
		help=f"Stroke to disambiguate conflicts. Entries that end with this stroke will not be included")
args=parser.parse_args()

Outline=Tuple[str, ...]
dictionary: Dict[Outline, str]={
		tuple(outline.split("/")): translation
		for outline, translation in
			json.loads(args.dictionary.read_text())
			.items()}
if args.disambiguation_stroke:
	disambiguation_stroke: str=args.disambiguation_stroke
	dictionary={
			outline: translation
			for outline, translation in dictionary.items()
			if outline[-1]!=disambiguation_stroke}

word_to_strokes: Dict[str, List[Outline]]={
		word: [item[0] for item in items]
		for word, items in
		group_sort(dictionary.items(), key=lambda x: x[1])
		}

def process_ngram(ngram: List[str])->None:
	if len(ngram)==1: return
	try:
		entries=itertools.product(*(word_to_strokes[word] for word in ngram))
	except KeyError:
		return
	entry: Tuple[Outline, ...]
	for entry in entries:
		cat: Outline=sum(entry, ())
		for i in range(len(entry[0])+1, len(cat)+1):
			if cat[:i] in dictionary:
				expected_output: str=' '.join(ngram)
				actual_output: str=dictionary[cat[:i]]
				if expected_output!=actual_output:
					outline_: str="/".join(str(Stroke(x)) for x in cat)
					print(f"Conflict: {expected_output!r} -> {actual_output!r}" +
							('' if i==len(cat) else ' [...]') +
							f' ({outline_})')
					return  # only need to print one instance
				else:
					pass  # intentional multiple word definition

for ngram in json.loads(args.ngrams_file.read_text()):
	process_ngram(ngram.split())
