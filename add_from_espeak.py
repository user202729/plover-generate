#!/bin/python

import subprocess
from typing import List, Tuple

import argparse
import sys
parser=argparse.ArgumentParser(
		usage="Append to open-dict-additional.txt, use espeak to generate the pronunciation",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("words", help="List of words", nargs="*")
parser.add_argument("-n", "--dry-run", help="Print to stdout instead.", action="store_true")
args=parser.parse_args()
words: List[str]=[*dict.fromkeys(args.words)]
if not words: exit()

pronounces: List[str]=subprocess.check_output([
	"espeak",
	"-q",
	"--ipa",
	' '.join(words)
	]).decode('u8').split()


with (sys.stdout if args.dry_run else open("open-dict-additional.txt", "a")) as f:
	for word, pronounce in zip(words, pronounces):
		pronounce=pronounce.replace("əʊ", "oʊ").replace("ɜː", "əɹ").replace("eə", "ɛɹ"
				).translate({
			ord("l"): "ɫ",
			ord("r"): "ɹ",
			ord("ɐ"): "ə",
			ord("ɒ"): "ɑ",
			ord("ʌ"): "ə",
			ord("a"): "æ",  # temporary
			ord("ː"): "",
			}).replace("æɪ", "aɪ")
		assert not ({*pronounce}&{'l', 'r', 'ɐ', 'ɒ', 'ɜ', 'ʌ', 'ː'}), pronounce
		assert "əʊ" not in pronounce, pronounce
		f.write(f"{word}\t/{pronounce}/\n")
