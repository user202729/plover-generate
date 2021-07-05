#!/bin/pypy3
## ==== create a pronunciation dictionary (sort of)
## write to tempdir/out
## error remains...

import sys

import local_lib

try:
	del sys.modules["lib"]
except KeyError:
	pass

from lib import *

##

debug_print_all_matching=False

#ALL_LIMIT=10000  # most frequent
ALL_LIMIT=10**9
word_filter=lambda word: True
#word_filter=lambda word: word.lower() in {"thought", "though"}

frequency=frequency_()
pronunciation=pronunciation_()
plover_dict=plover_dict_()
plover_dict_by_frequency=plover_dict_by_frequency_(plover_dict, frequency)


print("done")

##

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
	with open(tempdir/"out", "w") as f, replace_stdout(f):
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

	with open(tempdir/"out2", "w") as f:
		for (s, p), words in sorted(
				used.items(),
				key=lambda x: -len(x[1])
				):
			#if not s or not p:
			if True:
				print(f"{s}\t{p}\t{str(words)[:100]}", file=f)
				##
