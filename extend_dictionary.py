#!/bin/python3
from pathlib import Path
from lib import *
import json
import argparse
parser=argparse.ArgumentParser(usage="Include implicit suffix-folded entries in the dictionary",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter
		)
parser.add_argument("dictionary", type=Path, help="Path to JSON dictionary.",
		default="main.json", nargs="?"
		)
parser.add_argument("-o", "--output", type=Path, default=None,
		help="Output file path. Defaults to stdout.")
parser.add_argument("--exclude-existing", action="store_true")
parser.add_argument("--double-check", action="store_true")
parser.add_argument("--print-double-check-error", action="store_true")
parser.add_argument("--disallowed-tsdz-shapes", default="-TZ,-SD,-TDZ,-TSD,-SDZ,-TSZ",
		help="Comma-separated list of strokes that must not be in a stroke.")
args=parser.parse_args()

warn_if_not_optimization()

from plover.registry import registry       # type: ignore
from plover import system                  # type: ignore

def add_suffix(word: str, suffix: str)->str:
	...
from plover.orthography import add_suffix  # type: ignore

registry.update()
system.setup("English Stenotype")

source: Dict[Strokes, str]={
		to_strokes(outline): translation
		for outline, translation in
		json.loads(Path(args.dictionary).read_text()).items()}
generated=dict(source)
frequency=frequency_()
base_form_lower: Dict[str, str]={
		word.lower(): base.lower()
		for word, base in base_form_().items()
		}

import re
suffix_extract_pattern=re.compile(r'{\^(\w+)}')
suffixes: Dict[Stroke, str]={suffix: match[1]
		for suffix_str in typing.cast(Sequence[str], system.SUFFIX_KEYS)
		for suffix in [Stroke(suffix_str)]
		if (suffix,) in source
		for match in [suffix_extract_pattern.fullmatch(source[suffix,])]
		if match is not None
		}
for suffix_stroke in suffixes: assert len(suffix_stroke)==1

tsdz_stroke=Stroke("-TSDZ")
disallowed_tsdz_shapes: Set[Stroke]={Stroke(x) for x in args.disallowed_tsdz_shapes.split(",")}
for x in disallowed_tsdz_shapes:
	assert x in tsdz_stroke, x

for outline, word in source.items():
	if word not in frequency: continue
	assert outline
	for suffix_stroke, suffix in suffixes.items():
		if suffix_stroke in outline[-1]: continue
		word_=add_suffix(word, suffix)
		if base_form_lower.get(word_.lower(), None)!=word.lower(): continue
		#if word_ not in frequency: continue
		new_last_outline=outline[-1]|suffix_stroke
		if (new_last_outline&tsdz_stroke) in disallowed_tsdz_shapes: continue
		outline_=outline[:-1]+(new_last_outline,)

		if outline_ in generated: continue

		if args.double_check:
			def fail()->bool:
				for i in range(1, len(outline_)):
					outline__part=outline_[i:]
					if outline__part not in source: continue
					if args.print_double_check_error:
						print(f"{outline}+{suffix_stroke} != {word!r}+{suffix} "
								f"because {outline_[i:]} = {source[outline__part]!r}",
								file=sys.stderr)
					return True
				for suffix_stroke1, suffix1 in suffixes.items():
					if suffix_stroke1==suffix_stroke: break
					if suffix_stroke1 not in outline_[-1]: continue
					outline1=outline_[:-1]+(outline_[-1]-suffix_stroke1,)
					if outline1 not in source: continue
					if args.print_double_check_error:
						print(f"{outline}+{suffix_stroke} !== {word!r}+{suffix} "
								f"because {outline1} = {source[outline1]!r}",
								file=sys.stderr)
					return True

				return False
			if fail(): continue

		generated[outline_]=word_

if args.exclude_existing:
	generated={outline: word for outline, word in generated.items() if outline not in source}

json.dump(
		{
			"/".join(x.raw_str() for x in outline): translation
			for outline, translation in generated.items()
			},
		sys.stdout if args.output is None else args.output.open("w"),
		indent=0, ensure_ascii=False)
