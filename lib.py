from pathlib import Path
from typing import List, Dict, Mapping, Optional, Sequence, Tuple, Set, Callable, Any, Iterable, Union, MutableMapping, Generic, TypeVar
import typing
import functools
import itertools
from time import time
import re
import sys
from collections import Counter
from collections import defaultdict
import json
import random
import enum
import tempfile


from contextlib import contextmanager
@contextmanager
def timing(info: Any):
	"""
	Simple context manager measure time taken by code.
	"""
	start=time()
	try:
		yield
	finally:
		duration=time()-start
		print(f"{duration:8.3f}:", info)

@contextmanager
def replace_stdout(f):
	backup=sys.stdout
	try:
		sys.stdout=f
		yield
	finally:
		sys.stdout=backup

from stroke import*

tempdir=Path(tempfile.gettempdir())

KeyType=TypeVar("KeyType")
ValueType=TypeVar("ValueType")
def group_sort(iterable: Iterable[ValueType], key: Callable[[ValueType], KeyType])->Iterable[
		Tuple[
			KeyType,
			Iterable[ValueType]
			]
		]:
	return itertools.groupby(sorted(iterable, key=key), key)  # type: ignore

def unordered_group(iterable: Iterable[ValueType], key: Callable[[ValueType], KeyType])->Iterable[
		Tuple[
			KeyType,
			List[ValueType]
			]
		]:
	items=defaultdict(list)
	for x in iterable: items[key(x)].append(x)
	return items.items()  # type: ignore

# it's simpler to remove the stressed marks first
# because otherwise it's necessary to handle the rules
# x -> ks, kˈs, kˌs, gz, gˈz, gˌz separately.

def remove_stressed_mark(pronounce: str)->str:
	return pronounce.translate({
		ord("ˌ"): "",
		ord("ˈ"): "",
		})

Strokes=Tuple[Stroke, ...]

# return the list of all keys, ignore empty strokes.
# example: /ST/-K => ["S-", "T-", "/", "-K"]
def flat_keys(outline: Strokes)->List[str]:
	flat_keys: List[str]=[]
	for stroke in outline:
		if stroke:
			if flat_keys: flat_keys.append("/")
			flat_keys.extend(stroke)
	return flat_keys

def to_strokes(s: str)->Strokes:
	return tuple(Stroke(x) for x in s.split("/"))




key_to_skey={
		key: (
			key[0].upper() if len(key)==2 and key[1]=="-" else
			key[1].lower() if len(key)==2 and key[0]=="-" else
			key
			)
		for key in Stroke.KEYS}
for x in key_to_skey.values(): assert len(x)==1
skey_to_key={
		skey: key for key, skey in key_to_skey.items()
		}
assert len(key_to_skey)==len(Stroke.KEYS)==len(skey_to_key)

# skey idea from spectra lexer.
# actually not a bad idea...?

def to_skeys(strokes: str)->str:
	return "/".join(
			"".join(map(key_to_skey.__getitem__, Stroke(stroke).keys()))
			for stroke in strokes.split("/")
			)

def from_skeys(skeys: str)->str:
	return "/".join(
			str(Stroke([*map(skey_to_key.__getitem__, stroke)]))
			for stroke in skeys.split("/")
			)

def frequency_()->Dict[str, float]:
	"""
	Return a dict that maps a word (with correct case) to the number of occurrences in 10**9 words.
	Frequency list taken from Wikipedia.
	"""
	frequency_=[
			(b, float(c))
			for a in Path("frequency-list").read_text().splitlines()
			for b, c in (a.split("\t"),)
			]
	frequency=dict(frequency_)
	assert len(frequency)==len(frequency_)
	return frequency
abbreviations={*"""
		aug feb
""".split()}


letter_spell_out={
"a": "eɪ",
"b": "bi",
"c": "si",
"d": "di",
"e": "i",
"f": "ɛf",
"g": "dʒi",
"h": "eɪtʃ",
"i": "aɪ",
"j": "dʒeɪ",
"k": "keɪ",
"l": "ɛɫ",
"m": "ɛm",
"n": "ɛn",
"o": "oʊ",
"p": "pi",
"q": "kju",
"r": "ɑɹ",
"s": "ɛs",
"t": "ti",
"u": "ju",
"v": "vi",
"w": "dəbəɫju",
"x": "ɛks",
"y": "waɪ",
"z": "zi",
}

def spell_out(word: str)->Optional[str]:
	try:
		return "".join(letter_spell_out[x] for x in word)
	except KeyError:
		return None

def pronunciation_(p: Path)->Dict[str, List[str]]:
	"""
	For each word spelling (lower case), return a list of pronunciation in open-dict's IPA format.
	"""
	pronunciation_=[
			(word, pronunciations_filtered)
			for a in p.read_text().splitlines()
			for word, pronunciations in (a.split("\t"),)
			for pronunciations_filtered in [[
					pronunciation
					for pronunciation_ in pronunciations.split(", ")
					for pronunciation in [pronunciation_
						.strip("/")  # the pronunciation is stored in the file as /<actual pronunciation>/
						.replace("ɝɹ", "əɹ")
						.replace("ɝ", "əɹ")]  # the dictionary uses both convention. ər is easier to process.
					if remove_stressed_mark(pronunciation)!=spell_out(word)
			]]
			if pronunciations_filtered
			and {*word}&{*"aeiouy"}
			and "." not in word  # otherwise it's an abbreviation
			and word not in abbreviations
			]
	pronunciation=dict(pronunciation_)
	assert len(pronunciation)==len(pronunciation_)
	return pronunciation
def plover_dict_()->Dict[str, str]:
	plover_dict=json.loads(
			Path("main.json")
			#Path("di-dictionary.json")
			.read_text())
	return plover_dict

def plover_dict_by_frequency_(plover_dict: Dict[str, str], frequency: Dict[str, float]) -> List[Tuple[
		float,  # frequency
		str, # word
		List[str]  # entries
		]]:
	return [
				(-negative_frequency, word, [outline for outline, word in plover_entries])
				for (negative_frequency, word), plover_entries in group_sort(
					plover_dict.items(),
					key=lambda x: (-frequency.get(x[1].lower(), 0), x[1])
					)
				]

def base_form_()->Dict[str, str]:
	return {
			word: base
			for line in Path("lemmatization.txt").read_text().splitlines()
			for base, word in [line.split()]
			}
	
from dataclasses import dataclass

@dataclass(frozen=True)
class MatchRule:
	pass

@dataclass(frozen=True)
class FailedSpell(MatchRule):
	spell: str

@dataclass(frozen=True)
class FailedPronounce(MatchRule):
	pronounce: str

MatchCondition=Callable[[
	"Matched",
	str, str,
	int, int
	], bool] # see meanings of parameters in always_match function parameters

def always_match(rule: Any, spell: str, pronounce: str, spell_pos: int, pronounce_pos: int)->bool:
	return True

@dataclass(frozen=True)
class Matched(MatchRule):
	spell: str
	pronounce: str
	condition: MatchCondition=always_match
	score: float=0  # smaller is better

def and_condition(a: MatchCondition, b: MatchCondition)->MatchCondition:
	return (
			lambda rule, spell, pronounce, spell_pos, pronounce_pos:
			a(rule, spell, pronounce, spell_pos, pronounce_pos) and
			b(rule, spell, pronounce, spell_pos, pronounce_pos)
			)

def regex_spell_condition(x: Union[re.Pattern, str])->MatchCondition:
	y: re.Pattern=re.compile(x) if isinstance(x, str) else x

	# x:   <before><...><after>
	def result(rule: Matched, spell: str, pronounce: str, spell_pos: int, pronounce_pos: int)->bool:
		return y.search(
				spell[:spell_pos] + "<" +
				spell[spell_pos:spell_pos+len(rule.spell)] + ">" +
				spell[spell_pos+len(rule.spell):]
				) is not None
	return result

def regex_pronounce_condition(x: Union[re.Pattern, str])->MatchCondition:
	y: re.Pattern=re.compile(x) if isinstance(x, str) else x

	# x:   <before><...><after>
	def result(rule: Matched, spell: str, pronounce: str, spell_pos: int, pronounce_pos: int)->bool:
		return y.search(
				pronounce[:pronounce_pos] + "<" +
				pronounce[pronounce_pos:pronounce_pos+len(rule.pronounce)] + ">" +
				pronounce[pronounce_pos+len(rule.pronounce):]
				) is not None

	return result

def regex_condition(
		spell: Union[re.Pattern, str],
		pronounce: Union[re.Pattern, str],
		)->MatchCondition:
	return and_condition(regex_spell_condition(spell), regex_pronounce_condition(pronounce))


leading: MatchCondition=(
		lambda rule, spell, pronounce, spell_pos, pronounce_pos:
		spell_pos==0 and pronounce_pos==0
		)

# TODO
unstressed: MatchCondition=(
		lambda rule, spell, pronounce, spell_pos, pronounce_pos:
		True
		)

trailing: MatchCondition=(
		lambda rule, spell, pronounce, spell_pos, pronounce_pos:
		spell_pos==len(spell)-len(rule.spell) and pronounce_pos==len(pronounce)-len(rule.pronounce)
		)

#whole_word: MatchCondition=and_condition(leading, trailing)

@dataclass(frozen=True)
class MatchResult:
	rule: MatchRule
	spell_pos: int # starting position
	pronounce_pos: int


# https://www.dictionary.com/e/key-to-ipa-pronunciations/
# TODO are the conditions really necessary?...
rules: List[Matched]=[
# special: stressed mark
#Matched("", "ˌ"),
#Matched("", "ˈ"),


Matched("b", "b"),
Matched("bb", "b"),
Matched("d", "d"),
Matched("dd", "d"),
Matched("dg", "dʒ"),
Matched("g", "dʒ"),
Matched("gg", "dʒ"),
Matched("d", "dʒ"),
Matched("j", "dʒ"),
Matched("dj", "dʒ"), # weird origin
Matched("f", "f"),  Matched("f", "v"),
Matched("ff", "f"),
Matched("ph", "f"), Matched("ph", "v"),
Matched("g", "ɡ"),
Matched("gg", "ɡ"),
Matched("h", "h"),
Matched("c", "k"),
Matched("cc", "k"),
Matched("ck", "k"),
Matched("k", "k"),
Matched("l", "ɫ"),
Matched("ll", "ɫ"),
Matched("m", "m"),
Matched("mm", "m"),
Matched("n", "n"),
Matched("nn", "n"),
Matched("n", "ŋ", score=0.1),
Matched("ng", "ŋ"),
Matched("ng", "ŋk", condition=regex_spell_condition("<ng>th")),
Matched("nc", "ŋ"),
Matched("nch", "ŋk"),
Matched("ch", "k"),
Matched("p", "p"),
Matched("pp", "p"),
Matched("r", "ɹ"),
Matched("rr", "ɹ"),
Matched("t", "t"),
Matched("tt", "t"),

Matched("c", "s"),
Matched("sc", "s"),
Matched("sc", "ʃ", score=0.1),
Matched("s", "s"),
Matched("ss", "s"),
Matched("sh", "ʃ"),
Matched("ch", "ʃ", score=0.1),  # tch -> tʃ should be atomic
Matched("sch", "ʃ"),
Matched("sci", "ʃ"),

Matched("sti", "ʃ",),
Matched("ti", "ʃ",),
Matched("tu", "ʃ",),
Matched("tu", "tʃ",),
Matched("ci", "ʃ",),
Matched("si", "ʒ"),
Matched("xi", "kʃ"),  # ksi -> ksh
Matched("su", "ʒ"),

Matched("ch", "tʃ"),
Matched("tch", "tʃ"),
Matched("th", "θ"),
Matched("th", "ð"),
Matched("v", "v"),
Matched("w", "w"),
Matched("wh", "hw"),
Matched("wh", "h", score=0.1),
#Matched("wh", "hˈw"),
Matched("wh", "w", score=0.1),
Matched("s", "z"),
Matched("ss", "z"),
Matched("z", "z"),
Matched("zz", "z"),
Matched("g", "ʒ"),

Matched("s", "ʃ", score=0.1),
Matched("s", "ʒ", score=0.1),
Matched("ss", "ʃ", score=0.1),
Matched("t", "tʃ", score=0.1),
Matched("t", "ʃ", score=0.1),
Matched("c", "ʃ", score=0.1),
Matched("c", "tʃ", score=0.1, condition=and_condition(
	regex_spell_condition("<c>e"), regex_pronounce_condition("<tʃ>e")
	)),

Matched("cq", "k"),
Matched("q", "k"),
Matched("u", "w"),
#*[
#match
#for spell, (a, b) in (
Matched("x", "ks"),
Matched("x", "kʃ"),
Matched("xh", "ks"),
Matched("x", "ɡz"),
Matched("xh", "ɡz"),
Matched("xc", "ks"),
#)
#for match in (
#Matched(spell, a+b),
#Matched(spell, a+"ˈ"+b),
#Matched(spell, a+"ˌ"+b),
#)
#],
Matched("h", "", condition=regex_spell_condition("^<h>|r<h>")),  # some word origin
Matched("t", "", condition=regex_spell_condition("s<t>le")),
Matched("d", "", condition=regex_pronounce_condition("n<>[szɫ]")),
Matched("w", "", condition=regex_spell_condition("^<w>[hr]")),
Matched("k", "", condition=regex_spell_condition("^<k>n")),
Matched("p", "", condition=regex_spell_condition("^<p>[fns]")),
Matched("b", "", condition=regex_spell_condition("m<b>|<b>t")),
Matched("n", "", condition=regex_spell_condition("m<n>")),
Matched("g", "", condition=regex_spell_condition("in<g>$|i<g>"), score=0.1),
Matched("-", ""),
Matched(" ", ""),


# (be extremely relaxed in the vowel matching)
*[
match
for spell in """
a aa
ai ay ei ey
al all au aw

e
ea ee eo

i y ia ui ieu
eye ie

o
ou 
oe
ow owe
oi oy

oa oo

u
eu ew ue
""".split()
for pronounce in """
æ
eɪ
ɑ

ɛ
i

ɪ ɪə
aɪ aɪə

ɔ
oʊ
aʊ
ɔɪ

ə ʊ
u ju jʊ jə
""".split()
for match in [Matched(spell, pronounce)]
],

Matched("u", "əw"),
Matched("i", "j"),
Matched("y", "j"),
Matched("gh", "f"),

Matched("gh", "", condition=regex_spell_condition("[aoeuiy]<gh>")),
Matched("u", "", condition=regex_spell_condition("q<u>e$")),
Matched("e", "", score=0.1),



Matched("o", "wə", condition=regex_spell_condition("<o>ne")),
#Matched("age", "ɪdʒ", condition=trailing),
Matched("gh", "ɡ"),
#Matched("l", "əɫ"),
#Matched("es", "z", condition=trailing),
Matched("ed", "t", condition=trailing),
#Matched("ed", "d", condition=trailing),
#Matched("ce", "s", condition=trailing),
#Matched("l", "", condition=regex_spell_condition("ou<l>d")),



Matched("'t", "t", condition=regex_spell_condition("n<'t>$")),
Matched("'ll", "ɫ", condition=trailing),
Matched("n't", "ən", condition=trailing),
Matched("s'", "z", condition=trailing),
Matched("'s", "s", condition=trailing),
Matched("'s", "z", condition=trailing),
Matched("'ve", "v", condition=trailing),
Matched("'d", "d", condition=trailing),
Matched("'re", "ɹ", condition=trailing),

Matched("ei", "ɪ", score=0.1),
]  # (are the conditions really necessary?...)

index,=[i for i, x in enumerate(rules) if x==Matched("ei", "ɪ")]
del rules[index]

special_cases: Set[Tuple[str, str]]={
("of", "əv"),
("for", "fɹəɹ"),
("good", "ɡɪd"),
("us", "juɛs"),

# uncommon abbreviations
("o'", "oʊ"),
("ne'er", "nɛɹ"),
("'em", "əm"),
("'tis", "tɪz"),
("ma'am", "mæm"),
("'cause", "kəz"),
}


spell_pronounce_to_rule={
		(rule.spell, rule.pronounce): rule
		for rule in rules
		}
assert len(rules)==len(spell_pronounce_to_rule), [x for x in spell_pronounce_to_rule if
		sum((r.spell, r.pronounce)==x for r in rules)>=2]


spelling_to_rule: Mapping[str, List[Matched]]={
		spell: [*rules]
		for spell, rules in group_sort(rules, key=lambda x: x.spell)
		if spell!=""
		}

pronunciation_to_rule: Mapping[str, List[Matched]]={
		pronounce: [*rules]
		for pronounce, rules in group_sort(rules, key=lambda x: x.pronounce)
		}

assert "" not in spelling_to_rule


def count_failed(result: List[MatchResult])->int:
	return sum(not isinstance(x.rule, Matched) for x in result)

int_infinity=1<<30

@functools.lru_cache(maxsize=None)
def match(spell: str, pronounce: str)->List[MatchResult]:
	assert pronounce==remove_stressed_mark(pronounce)

	

	match: List[List[List[MatchResult]]]=[
			[typing.cast(List[MatchResult], None)]*(len(pronounce)+1) for _ in range(len(spell)+1)]
	# match[a][b] = optimal for matching of spell[a:] - pronounce[b:]

	for a in range(len(spell), -1, -1):
		for b in range(len(pronounce), -1, -1):
			# a, b: left index for spell/pronounce
			if a==len(spell) and b==len(pronounce):  # base case
				match[a][b]=[]
				continue

			assert a<=len(spell)
			assert b<=len(pronounce)

			result: Optional[List[MatchResult]]=None
			result_score: float=int_infinity

			tmp_pronounce=pronounce[b:]
			for i in range(a+1, len(spell)+1):
				for rule in spelling_to_rule.get(spell[a:i], ()):
					if (tmp_pronounce.startswith(rule.pronounce) and
							rule.condition(  # type: ignore  # mypy error?...
								rule, spell, pronounce, a, b
								)
							):
						tmp=match[i][b+len(rule.pronounce)]
						new_score=count_failed(tmp)+rule.score
						if new_score<result_score:
							result=[MatchResult(rule, a, b)]+tmp
							result_score=new_score

			if a<len(spell):
				tmp=match[a+1][b]
				new_score=count_failed(tmp)+1
				if new_score<result_score:
					result=[MatchResult(FailedSpell(spell[a]), a, b)]+tmp
					result_score=new_score

			if b<len(pronounce):
				tmp=match[a][b+1]
				new_score=count_failed(tmp)+1
				if new_score<result_score:
					result=[MatchResult(FailedPronounce(pronounce[b]), a, b)]+tmp
					result_score=new_score

			assert result is not None

			match[a][b]=result


	return match[0][0]

def spell_of(matches: List[MatchResult])->str:
	spell=""
	for y in matches:
		r=y.rule
		if isinstance(r, FailedPronounce):
			pass
		else:
			assert isinstance(r, FailedSpell) or isinstance(r, Matched)
			spell+=r.spell
	return spell


def pronounce_of(matches: List[MatchResult])->str:
	pronounce=""
	for y in matches:
		r=y.rule
		if isinstance(r, FailedSpell):
			pass
		else:
			assert isinstance(r, FailedPronounce) or isinstance(r, Matched)
			pronounce+=r.pronounce
	return pronounce

def get_result_matching(result: List[MatchResult], color: bool=True)->Tuple[str, str]:
	"""
	Get a visual (ASCII table) representation for a spell-pronounce matching.
	"""
	spell_=""
	pronounce_=""
	for y in result:
		r=y.rule
		a=spell_of([y])
		b=pronounce_of([y])
		l=max(len(a), len(b))
		a=a.ljust(l)
		b=b.ljust(l)
		if color and not isinstance(r, Matched):
			from colorama import Fore  # type: ignore
			a=Fore.RED+a+Fore.RESET
			b=Fore.RED+b+Fore.RESET
		spell_+=a+"|"
		pronounce_+=b+"|"

	return spell_, pronounce_

def print_result_matching(result: List[MatchResult], color: bool=True)->None:
	"""
	Print a visual (ASCII table) representation for a spell-pronounce matching.
	"""
	spell_, pronounce_=get_result_matching(result, color)
	print("==", spell_)
	print("==", pronounce_)


vowel_pronounce_characters: Set[str]={*"aæɑeəɛiɪoɔuʊ"}
vowel_pronounce_characters_with_j: Set[str]=vowel_pronounce_characters|{"j"}
def fix_match(x: List[MatchResult])->List[Tuple[str, str]]:
	# group the vowels together
	# Tuple[str, str] type: (spell, pronounce)
	# (...)
	spell={*"aeiouy"}

	def is_vowel(x: Tuple[str, str])->bool:
		return not ({*x[0]}-spell) and not ({*x[1]}-vowel_pronounce_characters_with_j)

	def can_merge(a: Tuple[str, str], b: Tuple[str, str])->bool:
		return is_vowel(a) and is_vowel(b) and (not a[1] or not b[1])

	result: List[Tuple[str, str]]=[]
	for a in x:
		b=(spell_of([a]), pronounce_of([a]))
		if result and can_merge(result[-1], b):
			result[-1]=(result[-1][0]+b[0], result[-1][1]+b[1])
		else:
			result.append(b)
	return result

def warn_if_not_optimization()->None:
	try:
		assert False
	except AssertionError:
		print("Note: assertions are enabled. May slow down the program.", file=sys.stderr)
