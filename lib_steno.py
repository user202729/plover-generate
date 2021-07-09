if "lib_steno_initialized" in globals():
	raise RuntimeError("This part is not supposed to be run twice")
lib_steno_initialized=True


from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterator, Sequence, Collection, TypeVar, MutableSequence
import enum

from lib import*

T=TypeVar("T", bound=type)
def nice_enum(cls: T)->T:

	def repr_(self)->str:
		return str(self)

	def eq_(self, other):
		assert type(other) is type(self)
		return super(cls, self).__eq__(other)
	
	cls.__repr__=repr_  # type: ignore
	cls.__eq__=eq_  # type: ignore
	return cls

@nice_enum
class Stress(enum.Enum):
	none=enum.auto()  # there's no stress in the whole syllable
	no  =enum.auto()  # not stressed
	up  =enum.auto()  # stressed (ˈ)
	down=enum.auto()  # second stress (ˌ)

@dataclass(frozen=True)
class Match:
	spell: str
	pronounce: str
	stress: Stress

Matches=Tuple[Match, ...]

@nice_enum
class State(enum.Enum):
	outline_start  =enum.auto()
	prefix         =enum.auto()  # right after a prefix
	left           =enum.auto()
	vowel          =enum.auto()  # a vowel has just been added (most of the time same as (right))
	right          =enum.auto()
	right_separate =enum.auto()  # right, but in a separate stroke
	suffix         =enum.auto()  # right after a suffix

	def complete(self)->bool:
		return self in (State.vowel, State.right, State.right_separate, State.suffix)


@dataclass(frozen=True)
class S:
	strokes: Strokes
	state: State
	seen_schwa_in_cluster: bool  # current (left or right) cluster
	mark: bool  # for debugging.

S_default=S((), State.outline_start, False, False)

@dataclass
class StenoRule:
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		raise NotImplementedError

@dataclass
class StenoRulePrefix(StenoRule): # prefix in a separate stroke
	a: Stroke
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if s.state in (State.outline_start, State.prefix):
			yield S(s.strokes+(self.a,), State.prefix, False, s.mark)

@dataclass
class StenoRuleSuffix(StenoRule): # suffix in a separate stroke
	a: Stroke
	try_join: bool  # attempt to join this into the last stroke, if possible
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if (s.state==State.prefix or # allow an outline to consist of only prefixes and suffixes (but not only suffixes)
				s.state.complete()):
			yield S(
					(stroke_append(s.strokes, self.a) or s.strokes+(self.a,))
					if self.try_join else
					s.strokes+(self.a,)
					, State.suffix, False, s.mark)

@dataclass
class StenoRuleSuffixS(StenoRule): # suffix in a separate stroke
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if s.state.complete():
			yield S(
					s.strokes[:-1]+(s.strokes[-1]+Stroke("-SZ"),)
					if (s.strokes[-1]&Stroke("-TSDZ"))==Stroke("-TD") else
					(
						stroke_append(s.strokes, Stroke("-S")) or
						stroke_append(s.strokes, Stroke("-Z")) or
						s.strokes+(Stroke("-S"),)
						),
					State.suffix, False, s.mark)

@dataclass
class StenoRuleConsonant(StenoRule):
	a: Stroke
	b: Stroke
	dupe: bool
	# if type is consonant, a is left half and b is right half (**must** not be zero)
	#     if zero => none
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if s.state==State.suffix:
			return

		elif s.state in (State.outline_start, State.prefix):
			# separate left
			if self.a:
				yield S(s.strokes+(self.a,), State.left, False, s.mark)

		elif s.state==State.left:
			# try to put in the left part (if fail, separate left)
			if self.a:
				t=stroke_append(s.strokes, self.a)
				if t is not None:
					yield S(t, State.left, s.seen_schwa_in_cluster, s.mark)
				elif len(s.strokes)==1 and not s.seen_schwa_in_cluster:
					# only allow one separate leading consonant at the start of the word
					# without any prefix strokes
					# and with no schwa seen
					# (although having prefix strokes might still work because of orthographic rules)
					# left separate is not frequent in Plover theory
					# a set of possible onset may be better
					yield S(s.strokes+(self.a,), State.left, s.seen_schwa_in_cluster, s.mark)

		else:
			# try to put in the right (if fail, separate right)
			assert s.state in (State.vowel, State.right, State.right_separate)
			if self.b:
				t=stroke_append(s.strokes, self.b)
				if t is not None:
					yield S(t,
							State.right_separate if s.state==State.right_separate else State.right,
							s.seen_schwa_in_cluster, s.mark)
				elif s.state!=State.right_separate and not s.seen_schwa_in_cluster:
					# disallow double right_separate
					# example: [extr] cannot be a "natural" syllable (EX/-T/-R)
					# (besides, it's stroke-inefficient)
					# also disallow when there's a schwa in the cluster
					# right_separate is not frequent in Plover theory
					yield S(s.strokes+(self.b,),
							State.right_separate, s.seen_schwa_in_cluster, s.mark)

				# try to put in right+left (if (right) fail, ignore)
				assert not self.dupe
				pass

			# try to make a new syllable (this syllable has a vowel already)
			if self.a:
				yield S(s.strokes+(self.a,), State.left, False, s.mark)


@dataclass
class StenoRuleVowel(StenoRule):
	a: Stroke
	# a can be zero
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		t: Strokes
		if s.state==State.suffix:
			return

		elif s.state==State.left:
			# put it in
			t_=stroke_append(s.strokes, self.a)
			assert t_ is not None
			t=t_

		else:
			assert s.state in (State.outline_start, State.prefix, State.vowel, State.right, State.right_separate)
			# leave it in a new stroke
			t=s.strokes+(self.a,)

		yield S(t, State.vowel,
				False,
				s.mark or s.state==State.vowel # (debug) mark consecutive vowels
				)

@dataclass
class StenoRuleSkipSchwa(StenoRule):
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if not s.seen_schwa_in_cluster:
			s=S(strokes=s.strokes, state=s.state, seen_schwa_in_cluster=True, mark=s.mark)
		yield s

@dataclass
class StenoRuleSkip(StenoRule):
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		yield s

@dataclass
class StenoRuleCombine(StenoRule):
	a: StenoRule
	b: StenoRule
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		for t in self.a.apply(s, (), -1, -1):
			yield from self.b.apply(t, (), -1, -1)

##


def print_matches(x: Matches)->None:
	spell_, pronounce_="", ""
	for i, y in enumerate(x):
		s, p=y.spell, y.pronounce
		if i: spell_+="|"; pronounce_+="|"
		l=max(len(s), len(p))
		spell_+=s.rjust(l)
		pronounce_+=p.rjust(l)
	print(spell_)
	print(pronounce_)

vowel_diphthongs: Set[Tuple[str, str]]={
		("a", "ɪ"),
		("a", "ʊ"),
		("e", "ɪ"),
		("ɔ", "ɪ"),
		("o", "ʊ"),
		("ə", "ʊ"),
		}
def matched_pronunciation_dictionary_(p: Path)->List[Matches]:
	"""
	Read and return a matched pronunciation dictionary (as outputted by main2).
	The spelling is in lowercase.
	"""
	items: List[Matches]=[]
	
	for component_ in p.read_text().split("\n\n"):
		component=component_.splitlines()
		if not component: continue
		if component[0].startswith("++"): del component[0]
		if not component: continue
		spell_, pronounce_=component
		spell=[x.strip() for x in spell_.split("|")]
		pronounce__, pronounce_original=pronounce_.split("#")
		pronounce=[x.strip() for x in pronounce__.split("|")]

		assert "".join(pronounce)==remove_stressed_mark(pronounce_original)
		result=[Match(a, b, Stress.none) for a, b in zip(spell, pronounce)]
		if {*pronounce_original}&{*"ˈˌ"}:
			stress=Stress.no
			i=0
			for j, x in enumerate(result):
				for c in x.pronounce:
					while True:
						d=pronounce_original[i]
						i+=1
						if d=="ˈ":
							assert stress==Stress.no
							stress=Stress.up
						elif d=="ˌ":
							assert stress==Stress.no
							stress=Stress.down
						else:
							assert d==c
							break
				if {*x.pronounce}&vowel_pronounce_characters:
					if stress==Stress.no and j!=0 and (result[j-1].pronounce, x.pronounce) in vowel_diphthongs:
						result[j]=Match(x.spell, x.pronounce, result[j-1].stress)
					else:
						result[j]=Match(x.spell, x.pronounce, stress)
						stress=Stress.no
				else:
					result[j]=Match(x.spell, x.pronounce, Stress.no)
			assert i==len(pronounce_original)

		items.append(tuple(result))

	return items

def stroke_concatenate(a: Stroke, b: Stroke)->Optional[Stroke]:
	if a and b and not (a&not_star).is_prefix(b&not_star):
		return None
	return a|b

def stroke_append(a: Strokes, b: Stroke)->Optional[Strokes]:
	"""
	Try to tuck stroke b into the last stroke of a.
	Return None if a is empty, or b doesn't fit into the last stroke of a.
	"""
	if not a: return None
	c=stroke_concatenate(a[-1], b)
	if c is not None: return a[:-1]+(c,)
	return None


def spell_of_(x: Sequence[Match])->str:
	return "".join(y.spell for y in x)

def pronounce_of_(x: Sequence[Match])->str:
	return "".join(y.pronounce for y in x)

		#[["ai", "aigh", "ay", "ei", "eigh", "ey", ], "AEU",  ],
		#[["al", "all", "augh", "au", "aw",        ], "AU",   ],
		#[["ea", "ee", "eo",                       ], "AOE",  ],
		#[["eye", "ie", "igh", "ig",               ], "AOEU", ],
		#[["ou", "ough",                           ], "OE",   ],
		#[["ow", "owe",                            ], "OU",   ],
		#[["oi", "oy",                             ], "OEU",  ],
		#[["eu", "ew", "ue",                       ], "AOU",  ],
		#[["oa", "oo",                             ], "AO",   ],


skip_rule: StenoRule=StenoRuleSkip()
schwa_skip_rule: StenoRule=StenoRuleSkipSchwa()

steno_rules_by_spell: Dict[str, List[StenoRule]]={}  # spell -> rule
steno_rules_by_both: Dict[Tuple[str, str], List[StenoRule]]={}  # (spell, pronounce) -> rule
steno_rules_by_pronounce: Dict[str, List[StenoRule]]={}  # less priority & hidden than the above
steno_rules_by_pronounce_no_hide: Dict[str, List[StenoRule]]={}  # independent, never hidden
# these code will be populated by the code below
# they're not the complete set of rules. See also get_steno_rules and fix_outline.
# to clarify, these are only internal implementation details of get_steno_rules function.

# vowel
x1: List[str]
for pronounce, stroke, x1 in [  # type: ignore
		("æ     ", "A     ", []),

		("aɪ    ", "AOEU  ", []),
		("aɪə   ", "AOEU  ", []),

		("aʊ    ", "OU    ", []),

		("ɛ     ", "E     ", [
			"a ai ei ay      | AEU   "
			]),
		("eɪ    ", "AEU   ", []),

		("ɪ     ", "EU    ", [
			"ee ea ie e      | AOE  ",
			]),
		("i     ", "AOE   ", [
			"y i             | EU   ",
			]), # may be /iː/ but open ipa dict does not use /ː/

		("ɔ     ", "AU    ", [
			"o ou            | O    ",
			"oa              | AO AU",
			"a               | A",
			]),
		("ɑ     ", "O     ", [
			"ea              | A    ",
			"a               | A    ",
			"au              | AU   ",
			]),

		("oʊ    ", "OE    ", [
			"oa              | AO OE",
			]),
		("əʊ    ", "OE    ", [
			"oa              | AO OE",
			]),

		("ɔɪ    ", "OEU   ", []),

		("ju    ", "AOU   ", []),
		("jʊ    ", "AOU   ", []),

		("u     ", "AOU   ", [
			"oo              | AO   ",
			"o               | O    ",
			"ou              | OU AOU",
			]),
		("ʊ     ", "U     ", [
			"oo              | AO   ",
			"o               | O    ",
			]),

		("wə    ", "U     ", []),    # (temporary)
		("əw    ", "U     ", []),    # (temporary)
		("jə    ", "U     ", []),
		("ə     ", "U     ", [
			"a aa           | A    ",
			"e ea           | E    ",
			"i y ia ui ieu  | EU   ",
			"o              | O    ",
			"u              | U    ",
			"ou             | OU U ",
			]), # this may be /ʌ/ too
]:
	pronounce=pronounce.strip()
	stroke=stroke.strip()
	assert pronounce not in steno_rules_by_pronounce, pronounce
	steno_rules_by_pronounce[pronounce]=[StenoRuleVowel(Stroke(stroke))]

	for line in x1:
		spells, strokes=line.split("|")
		for spell in spells.split():
			assert (spell, pronounce) not in steno_rules_by_both
			steno_rules_by_both[spell, pronounce]=[
					StenoRuleVowel(Stroke(stroke))
					for stroke in strokes.split()]

K=TypeVar("K")
V=TypeVar("V")
def append_(d: Dict[K, List[V]], key: K, value: V)->None:
	if key not in d:
		d[key]=[value]
	else:
		d[key].append(value)

assert ("o", "wə") not in steno_rules_by_both
steno_rules_by_both["o", "wə"]=[StenoRuleCombine(
		StenoRuleConsonant(Stroke("W"), Stroke(), False),
		StenoRuleVowel(Stroke("U")),
		)]

# prefix
append_(steno_rules_by_spell, "re      ".strip(), StenoRulePrefix(Stroke("RE       ".strip())))
append_(steno_rules_by_spell, "pre     ".strip(), StenoRulePrefix(Stroke("PRE      ".strip())))
append_(steno_rules_by_spell, "de      ".strip(), StenoRulePrefix(Stroke("TKE      ".strip())))
append_(steno_rules_by_spell, "for     ".strip(), StenoRulePrefix(Stroke("TPAUR    ".strip())))
append_(steno_rules_by_spell, "on      ".strip(), StenoRulePrefix(Stroke("AUPB     ".strip())))
append_(steno_rules_by_spell, "co      ".strip(), StenoRulePrefix(Stroke("KAU      ".strip())))
append_(steno_rules_by_spell, "or      ".strip(), StenoRulePrefix(Stroke("AUR      ".strip())))
append_(steno_rules_by_spell, "out     ".strip(), StenoRulePrefix(Stroke("AOUT     ".strip())))
append_(steno_rules_by_spell, "extra   ".strip(), StenoRulePrefix(Stroke("ERBGS    ".strip())))
append_(steno_rules_by_spell, "extra   ".strip(), StenoRulePrefix(Stroke("*ERBGS   ".strip())))
append_(steno_rules_by_spell, "mis     ".strip(), StenoRulePrefix(Stroke("PHEUZ    ".strip())))
append_(steno_rules_by_spell, "miss    ".strip(), StenoRulePrefix(Stroke("PHEUZ    ".strip())))
append_(steno_rules_by_spell, "e       ".strip(), StenoRulePrefix(Stroke("AOE      ".strip())))
append_(steno_rules_by_spell, "super   ".strip(), StenoRulePrefix(Stroke("SPR      ".strip())))
append_(steno_rules_by_spell, "super   ".strip(), StenoRulePrefix(Stroke("SAOUP    ".strip())))
append_(steno_rules_by_spell, "under   ".strip(), StenoRulePrefix(Stroke("UPBD     ".strip())))
append_(steno_rules_by_spell, "con     ".strip(), StenoRulePrefix(Stroke("KAUPB    ".strip())))
append_(steno_rules_by_spell, "ex      ".strip(), StenoRulePrefix(Stroke("EBGS     ".strip())))
append_(steno_rules_by_spell, "exc     ".strip(), StenoRulePrefix(Stroke("EBGS     ".strip())))

# suffix
append_(steno_rules_by_spell, "able     ".strip(), StenoRuleSuffix(Stroke("-BL     ".strip()), False))
append_(steno_rules_by_spell, "ible     ".strip(), StenoRuleSuffix(Stroke("-BL     ".strip()), False))
append_(steno_rules_by_spell, "ible     ".strip(), StenoRuleSuffix(Stroke("EUBL    ".strip()), False))
append_(steno_rules_by_spell, "er       ".strip(), StenoRuleSuffix(Stroke("*ER     ".strip()), False))
append_(steno_rules_by_spell, "or       ".strip(), StenoRuleSuffix(Stroke("O*R     ".strip()), False))
append_(steno_rules_by_spell, "al       ".strip(), StenoRuleSuffix(Stroke("A*L     ".strip()), False))
append_(steno_rules_by_spell, "an       ".strip(), StenoRuleSuffix(Stroke("A*PB    ".strip()), False))
append_(steno_rules_by_spell, "en       ".strip(), StenoRuleSuffix(Stroke("*EPB    ".strip()), False))
append_(steno_rules_by_spell, "ol       ".strip(), StenoRuleSuffix(Stroke("O*L     ".strip()), False))
append_(steno_rules_by_spell, "on       ".strip(), StenoRuleSuffix(Stroke("O*PB    ".strip()), False))
append_(steno_rules_by_spell, "out      ".strip(), StenoRuleSuffix(Stroke("SKWROUT ".strip()), False))
append_(steno_rules_by_spell, "ure      ".strip(), StenoRuleSuffix(Stroke("AOUR    ".strip()), False))
append_(steno_rules_by_spell, "'s       ".strip(), StenoRuleSuffix(Stroke("AES     ".strip()), False))
append_(steno_rules_by_spell, "ly       ".strip(), StenoRuleSuffix(Stroke("HREU    ".strip()), False))
append_(steno_rules_by_spell, "li       ".strip(), StenoRuleSuffix(Stroke("HREU    ".strip()), False))
append_(steno_rules_by_spell, "ness     ".strip(), StenoRuleSuffix(Stroke("-PBS    ".strip()), False))
append_(steno_rules_by_spell, "less     ".strip(), StenoRuleSuffix(Stroke("-LS     ".strip()), False))
append_(steno_rules_by_spell, "ful      ".strip(), StenoRuleSuffix(Stroke("-FL     ".strip()), False))
append_(steno_rules_by_spell, "fully    ".strip(), StenoRuleSuffix(Stroke("TPHREU  ".strip()), False))
append_(steno_rules_by_spell, "some     ".strip(), StenoRuleSuffix(Stroke("SO*PL   ".strip()), False))
append_(steno_rules_by_spell, "some     ".strip(), StenoRuleSuffix(Stroke("SO*EPL  ".strip()), False))
append_(steno_rules_by_spell, "man      ".strip(), StenoRuleSuffix(Stroke("PHA*PB  ".strip()), False))
append_(steno_rules_by_spell, "ary      ".strip(), StenoRuleSuffix(Stroke("AER     ".strip()), False))
append_(steno_rules_by_spell, "ary      ".strip(), StenoRuleSuffix(Stroke("REU     ".strip()), False))
append_(steno_rules_by_spell, "ory      ".strip(), StenoRuleSuffix(Stroke("REU     ".strip()), False))
append_(steno_rules_by_spell, "ury      ".strip(), StenoRuleSuffix(Stroke("REU     ".strip()), False))
append_(steno_rules_by_spell, "tory     ".strip(), StenoRuleSuffix(Stroke("TOER    ".strip()), False))
append_(steno_rules_by_spell, "self     ".strip(), StenoRuleSuffix(Stroke("SEFL    ".strip()), False))
append_(steno_rules_by_spell, "selves   ".strip(), StenoRuleSuffix(Stroke("SEFLS   ".strip()), False))
append_(steno_rules_by_spell, "self     ".strip(), StenoRuleSuffix(Stroke("*S      ".strip()), True))
append_(steno_rules_by_spell, "selves   ".strip(), StenoRuleSuffix(Stroke("*S      ".strip()), True))
append_(steno_rules_by_spell, "istic    ".strip(), StenoRuleSuffix(Stroke("ST-BG   ".strip()), False))
append_(steno_rules_by_spell, "astic    ".strip(), StenoRuleSuffix(Stroke("ST-BG   ".strip()), False))
append_(steno_rules_by_spell, "ment     ".strip(), StenoRuleSuffix(Stroke("*PLT    ".strip()), False))
append_(steno_rules_by_spell, "le       ".strip(), StenoRuleSuffix(Stroke("-L      ".strip()), False))
append_(steno_rules_by_spell, "le       ".strip(), StenoRuleSuffix(Stroke("*L      ".strip()), False))
append_(steno_rules_by_spell, "ed       ".strip(), StenoRuleSuffix(Stroke("-D      ".strip()), True))
append_(steno_rules_by_spell, "ing      ".strip(), StenoRuleSuffix(Stroke("-G      ".strip()), True))

# some rules are sufficiently natural that the program can figure them out
# however if they're not explicitly listed as suffix, they cannot be used after (listed) suffixes

# suffix by pronounce
for line in [
		# (Plover theory) only if it's spelled with y? Not really. (cookie)
		"ɪ      KWREU  0",
		"i      KWREU  0",
		"kəɫ    K-L    0",
		"uəɫ    WAL    0",
		"wəɫ    WAL    0",
		]:
	pronounce, stroke, try_join=line.split()
	append_(steno_rules_by_pronounce_no_hide, pronounce, StenoRuleSuffix(Stroke(stroke), bool(int(try_join))))




# consonant by pronounce (and consonant cluster)
for line in [
		"b     | PW    | -B            ",
		"d     | TK    | -D            ",
		"dʒ    | SKWR  | -PBLG         ",
		"f     | TP    | -F            ",
		"ɡ     | TKPW  | -G            ",
		"k     | K     | -BG           ",
		"ɫ     | HR    | -L            ",
		"m     | PH    | -PL           ",
		"n     | TPH   | -PB           ",
		"p     | P     | -P            ",
		"ɹ     | R     | -R            ",
		"s     | S     | -S            ",
		"z     | S*    | -Z            ",
		"ʃ     | SH    | -RB           ",
		"ʒ     | SH    | -RB           ",
		"t     | T     | -T            ",
		"tʃ    | KH    | -FP           ",
		"θ     | TH    | *T            ",
		"ð     | TH    | *T            ",
		"v     | SR    | -F            ",
		"w     | W     | -             ",
		"hw    | WH    | -             ",
		"h     | H     | -             ",
		"j     | KWR   | -             ",
		"kʃən  | -     | -BGS  *BGS    ",
		"kʃɪn  | -     | -BGS  *BGS    ",
		"kʃn   | -     | -BGS  *BGS    ",
		"ŋ     | -     | -PBG          ",
		"ŋɡ    | -     | -PBG          ",
		"ndʒ   | -     | -PBG          ",
		"ŋk    | -     | *PBG          ",
		"ŋkʃən | -     | -PBGS         ",
		"ŋʃən  | -     | -PBGS         ",
		"mp    | -     | -FRP   *PL    ",
		"ɹv    | -     | -FRB          ",
		"st    | -     | *S            ",
		"kst   | -     | -GT    *BGS   ", # xt -> *x (Plover borrowed) -- with a special case below (ignore sed and ksed)
		"ks    | -     | -BGS          ", # -x
		"kʃ    | -     | -BGS          ", # -x (when followed by i → sound change)
		"ɡz    | -     | -BGS          ",
		"tʃən  | -     | -GS           ", # (weird dialect? open IPA dict use this for some -ʃən words)
		"ʃən   | -     | -GS           ",
		"ʒən   | -     | -GS           ",
		"dʒən  | -     | -GS           ",
		"ʃn    | -     | -GS           ",
		"ʃəs   | -     | -RBS          ",
		"dʒəs  | -     | -RBS          ",
		"ntʃ   | -     | -FRPB -FRPBLG ",
		"ɹtʃ   | -     | -FRPB         ",
		"ɫv    | -     | -FL           ",
		"ɹʃ    | -     | *RB           ",
		"kəmp  | KP    | -             ",
		"ɛks   | KP    | -             ",
		"ɛɡz   | KP    | -             ",
		"ɪks   | KP    | -             ",
		"ɪɡz   | KP    | -             ",
		]:
	pronounce, a, b=line.split("|")
	a_=[Stroke(x) for x in a.split()]
	b_=[Stroke(x) for x in b.split()]
	pronounce=pronounce.strip()
	assert pronounce not in steno_rules_by_pronounce, pronounce
	steno_rules_by_pronounce[pronounce]=[
			StenoRuleConsonant(a__, b__, False)
			for a__ in a_
			for b__ in b_
			]




# recall that steno_rules_by_both overrides steno_rules_by_pronounce, if there's a match.
# therefore don't use `-` arbitrarily.
# unless it's a compound, in that case both cases are considered.

# consonant by both
for line in [
		"s     | z   | S-         | -S   ",
		"se    | z   | S-         | -S   ",
		"ss    | z   | S-         | -S   ",
		"sse   | z   | S-         | -S   ",
		"h     |     | H          | -    ",
		"wh    | w   | WH         | -    ",
		"w     |     | W          | -    ",
		"c     | s   | S KR       | -S   ",
		"sc    | s   | S SK SKR   | -S   ",
		]:
	spell, pronounce, a, b=line.split("|")
	spell=spell.strip()
	pronounce=pronounce.strip()
	a_=[Stroke(x) for x in a.split()]
	b_=[Stroke(x) for x in b.split()]
	assert (spell, pronounce) not in steno_rules_by_both, (spell, pronounce)
	steno_rules_by_both[spell, pronounce]=[
			StenoRuleConsonant(a__, b__, False)
			for a__ in a_
			for b__ in b_
			]

def unstressed_schwa(match: Match)->bool:
	return match.pronounce in ("ə", "jə", "ɪ") and (
			# match.stress==Stress.no
			match.stress in (Stress.no, Stress.down)
			)

suffix_s_rule=StenoRuleSuffixS()

def get_steno_rules(whole: Matches, left: int, right: int)->Iterator[StenoRule]:
	assert left<right

	if right==left+1:
		if not whole[left].pronounce:
			yield skip_rule
			# ... consider other cases too...

	#if not whole[left].pronounce or not whole[right-1].pronounce:
	#	return  # to avoid duplicates, separate the empty unless it's inside the block

	# cannot apply this right now because empty pronounce parts can be matched

	pronounce=pronounce_of_(whole[left:right])
	spell=spell_of_(whole[left:right])

	if right==left+1 and left!=0 and unstressed_schwa(whole[left]):
		yield schwa_skip_rule
		# not return just yet. Consider normal cases too

	if right==left+1 and pronounce in ("s", "z") and spell=="s":
		yield suffix_s_rule

	try:
		yield from steno_rules_by_spell[spell]
	except KeyError:
		pass

	try:
		yield from steno_rules_by_pronounce_no_hide[pronounce]
	except KeyError:
		pass

	if (
			right==left+1 and right<len(whole)
			and whole[left].spell in ("i", "e")
			and whole[left].pronounce=="i"
			and {*whole[left+1].pronounce}&vowel_pronounce_characters_with_j
			):
		yield from steno_rules_by_pronounce["j"]
		return

	if "ed" in spell and pronounce in ("st", "kst"):
		assert right-left>=2
		return  # handle each part separately

	if spell=="oo":
		yield StenoRuleVowel(Stroke("AO"))
		return  # strict rule.

	if pronounce=="ŋk" and pronounce_of_(whole[right:]).startswith(("t", "ʃ")):
		yield from steno_rules_by_pronounce["ŋ"]  # not a strict rule

	if right==left+1 and pronounce=="ɔ" and spell_of_(whole[right:]).startswith("ll"):
		yield StenoRuleVowel(Stroke("AU"))
		return

	try:
		yield from steno_rules_by_both[spell, pronounce]
	except KeyError:
		try:
			yield from steno_rules_by_pronounce[pronounce]
		except KeyError:
			pass

def generate_iterator(whole: Matches, right: int)->Iterator[S]:
	# generate for whole[:right]. Need context
	if not right:
		yield S_default
		return
	for i in range(right-1,-1,-1):
		rules: List[StenoRule]=[*get_steno_rules(whole, i, right)]
		if rules:
			s: S
			for s in generate_(whole, i):
				for rule in rules:
					yield from rule.apply(s, whole, i, right)

@functools.lru_cache()
def generate_(whole: Matches, right: int)->Tuple[S, ...]:
	# like generate_iterator, but returns a tuple, and cached
	return tuple(generate_iterator(whole, right))

def generate(whole: Matches)->Tuple[S, ...]:
	# NOTE: need to filter out incomplete entries. See `generate_complete`
	return generate_(whole, len(whole))

def generate_complete(whole: Matches)->Tuple[S, ...]:
	return tuple(x for x in generate(whole) if x.state.complete())

right_half=Stroke("-FRPBLGTSDZ")

disallowed_suffixes: Set[Stroke]=set()
for line in [
		"A     ",
		"EU    ",
		"AOE   ",
		"AEU   ",
		]:
	stroke=Stroke(line.strip())
	assert stroke not in disallowed_suffixes
	for combining_suffix_ in [
			"",
			"-S",
			"-G",
			"-D",
			"-Z",
			]:
		combining_suffix=Stroke(combining_suffix_.strip())
		assert not combining_suffix or stroke.is_prefix(combining_suffix)
		disallowed_suffixes.add(stroke+combining_suffix)
disallowed_suffixes.remove(Stroke("AD"))

disallowed_prefixes: Set[Stroke]={Stroke(x.strip()) for x in [
	"EU",
	"AEU",
	]}


def fix_outline(x: Strokes)->Iterable[Strokes]:
	if len(x)>=2:
		if x[-1] in disallowed_suffixes:
			return
		if x[0] in disallowed_prefixes:
			return

	result: List[Stroke]=[]
	for s in x:
		if s in Stroke("-RPBLGTSDZ") and result and (result[-1]&right_half)==Stroke("-S"):
			result[-1]=result[-1]-Stroke("-S")+Stroke("-F")+s
		elif (s&right_half)==Stroke("-SD"):
			result.append(s-Stroke("-S")+Stroke("-F"))
		elif result and s==Stroke("-S") and (result[-1]&Stroke("-DZ"))==Stroke("-D"):
			result[-1]+=Stroke("-Z")
		else:
			result.append(s)

	yield tuple(result)

def generate_fixed(whole: Matches)->Tuple[Strokes, ...]:
	return tuple(dict.fromkeys(
		outline
		for x in generate_complete(whole)
		for outline in fix_outline(x.strokes)
		))  # remove duplicates while preserving the order
	
def plover_entry_matches_generated_1(plover_outline: Strokes, generated_outlines: Collection[Strokes])->bool:
	if plover_outline in generated_outlines: return True

	if len(plover_outline)==1:
		if star in plover_outline[0] and (plover_outline[0]-star,) in generated_outlines:
			return True
		if (plover_outline[0]&Stroke("AOEU"))==Stroke("AE"):  # ae can be ai or ee (could be ai/y or a/y too etc., but they're briefs instead of disambiguations)
			# TODO generate disambiguations
			if (plover_outline[0]|Stroke("U"),) in generated_outlines:
				return True
			if (plover_outline[0]|Stroke("O"),) in generated_outlines:
				return True
			if (plover_outline[0]-Stroke("A"),) in generated_outlines:
				return True

	return False

if "plover_initialized" not in globals():
	plover_initialized=False
	plover_main_dictionary=None
	# save some time...

def plover_translate(strokes: Strokes)->Optional[str]:
	"""
	Translate with Plover's dictionary.
	Return None if there's something else other than text.
	Does not special-case prefix/suffix.
	"""
	from plover_build_utils.testing import CaptureOutput        # type: ignore
	from plover.translation import Translation, Translator      # type: ignore
	from plover.formatting import Formatter                     # type: ignore
	from plover.steno import Stroke                             # type: ignore
	from plover.dictionary.json_dict import JsonDictionary      # type: ignore
	from plover.registry import registry                        # type: ignore
	from plover import system                                   # type: ignore
	from plover.steno import Stroke                             # type: ignore

	global plover_initialized, plover_main_dictionary
	if not plover_initialized:
		registry.update()
		system.setup("English Stenotype")

		plover_main_dictionary=JsonDictionary.load("main.json")

		plover_initialized=True

	output = CaptureOutput()
	formatter = Formatter();
	formatter.set_output(output)
	formatter.spaces_after=False
	formatter.start_attached=True
	translator = Translator(); translator.add_listener(formatter.format)

	dictionary = translator.get_dictionary()
	dictionary.set_dicts([plover_main_dictionary])

	# translate translations
	for stroke in strokes:
		translator.translate_stroke(Stroke(stroke.keys()))

	translator.flush()

	if len(output.instructions)!=1:
		return None

	type_, value=output.instructions[0]
	if type_!="s":
		return None
	return value
	# https://github.com/openstenoproject/plover/discussions/1242
