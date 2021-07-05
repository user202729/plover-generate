if "lib_steno_initialized" in globals():
	raise RuntimeError("This part is not supposed to be run twice")
lib_steno_initialized=True


from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterator, Sequence, Collection, TypeVar
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
	stroke_start   =enum.auto()
	left           =enum.auto()
	vowel          =enum.auto()  # a vowel has just been added (most of the time same as (right))
	right          =enum.auto()
	right_separate =enum.auto()  # right, but in a separate stroke

	def complete(self)->bool:
		return self in (State.vowel, State.right, State.right_separate)


@dataclass(frozen=True)
class S:
	strokes: Strokes
	state: State
	mark: bool  # for debugging.

@dataclass
class StenoRule:
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		raise NotImplementedError

@dataclass
class StenoRuleConsonant(StenoRule):
	a: Stroke
	b: Stroke
	dupe: bool
	# if type is consonant, a is left half and b is right half (**must** not be zero)
	#     if zero => none
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if s.state in (State.stroke_start, State.left):
			# try to put in the left part (if fail, separate left)
			if self.a:
				t=stroke_append(s.strokes, self.a)
				if t is not None or len(s.strokes)==1:
					# only allow one separate leading consonant at the start of the word
					# left separate is not frequent in Plover theory
					yield S(t or s.strokes+(self.a,), State.left, s.mark)

		else:
			# try to put in the right (if fail, separate right)
			assert s.state in (State.vowel, State.right, State.right_separate)
			if self.b:
				t=stroke_append(s.strokes, self.b)
				if t is not None or s.state!=State.right_separate:
					# disallow double right_separate
					# example: [extr] cannot be a "natural" syllable (EX/-T/-R)
					# (besides, it's stroke-inefficient)
					# right_separate is not frequent in Plover theory
					yield S(t or s.strokes+(self.b,), State.right_separate if t is None else State.right, s.mark)

				# try to put in right+left (if (right) fail, ignore)
				assert not self.dupe
				pass

			# try to make a new syllable (this syllable has a vowel already)
			if self.a:
				yield S(s.strokes+(self.a,), State.left, s.mark)


@dataclass
class StenoRuleVowel(StenoRule):
	a: Stroke
	# a can be zero
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		if s.state in (State.stroke_start, State.left):
			# put it in
			t=stroke_append(s.strokes, self.a)
			assert t is not None
		else:
			assert s.state in (State.vowel, State.right, State.right_separate)
			# leave it in a new stroke
			t=s.strokes+(self.a,)

		yield S(t, State.vowel, s.mark or s.state==State.vowel)
		# (debug) mark consecutive vowels

@dataclass
class StenoRuleSkip(StenoRule):
	def apply(self, s: S, whole: Matches, left: int, right: int)->Iterator[S]:
		yield s


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


def matched_pronunciation_dictionary_()->List[Matches]:
	items: List[Matches]=[]
	
	for component_ in Path("/tmp/out").read_text().split("\n\n"):
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
				if {*x.pronounce}&{*"aæɑeəɛiɪoɔuʊ"}:
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
	if not a: return (b,)
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

steno_rules_by_both: Dict[Tuple[str, str], Sequence[StenoRule]]={}  # (spell, pronounce) -> rule
steno_rules_by_pronounce: Dict[str, Sequence[StenoRule]]={}  # less priority than the above
# these code will be populated by the code below
# they're not the complete set of rules. See also get_steno_rules and fix_outline.


for line in [
	"æ     A   ",
	"aɪə   AOEU",
	"aɪ    AOEU",
	"aʊ    OU  ",
	"eɪ    AEU ",
	"wə    U   ",    # (temporary)
	"əw    U   ",    # (temporary)
	"jə    U   ",
	"ju    AOU ",
	"jʊ    AOU ",
	"oʊ    OE  ",
	"ɔɪ    OEU ",
	"u     AOU ",
	"ʊ     U   ",

	"ə     U   ", # this may be /ʌ/ too
	"ɔ     AU  ",
	"ɑ     O   ",
	"ɪ     EU  ",
	"i     AOE ", # may be /iː/ but open ipa dict does not use /ː/
	"ɛ     E   ",
	]:
	pronounce, stroke=line.split()
	assert pronounce not in steno_rules_by_pronounce, pronounce
	steno_rules_by_pronounce[pronounce]=(StenoRuleVowel(Stroke(stroke)),)

# special case by spelling.
# This completely overrides the default (by pronunciation) stroke,
# list them too if they should be kept in.
for pronounce_, x1 in [
	("ə", [
		 "a aa           | A    ",
		 "e ea           | E    ",
		 "i y ia ui ieu  | EU   ",
		 "o              | O    ",
		 "u              | U    ",
		 ]),
	
	("ɔ", [
		"o ou            | O    ",
		"oa              | AO AU",
		]),

	("oʊ əʊ", [
		"oa              | AO OE",
		]),

	("ʊ u", [
		"oo              | AO   ",
		]),

	("ɑ", [
		"a               | A    ",
		]),

	("ɪ", [
		"ee ea           | AOE  ",
		"e               | E    ",
		]),

	("i", [
		"y i             | EU   ",
		]),

	("ɛ", [
		"a ai            | AEU   "
		]),
	]:
	for pronounce in pronounce_.split():
		for line in x1:
			spells, strokes=line.split("|")
			for spell in spells.split():
				assert (spell, pronounce) not in steno_rules_by_both
				steno_rules_by_both[spell, pronounce]=[
						StenoRuleVowel(Stroke(stroke))
						for stroke in strokes.split()]


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
		"ŋ     | -     | -PBG          ",
		"ŋɡ    | -     | -PBG          ",
		"ndʒ   | -     | -PBG          ",
		"ŋk    | -     | *PBG          ",
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
for line in [
		"ed    | t   | -          | -D   ",
		"ed    | ɪd  | -          | -D   ",
		"s     | z   | S-         | -S   ",
		"se    | z   | S-         | -S   ",
		"ss    | z   | S-         | -S   ",
		"sse   | z   | S-         | -S   ",
		"ing   | ɪŋ  | -          | -G   ",
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

	if right==left+1 and unstressed_schwa(whole[left]):
		yield skip_rule
		# not return just yet. Consider normal cases too

	if (
			right==left+1 and right<len(whole)
			and whole[left].spell=="i"
			and whole[left].pronounce=="i"
			and whole[left+1].pronounce=="ə"
			):
		yield from steno_rules_by_pronounce["j"]
		return

	if "ed" in spell and pronounce in ("st", "kst"):
		assert right-left>=2
		return  # handle each part separately

	if spell=="oo":
		yield StenoRuleVowel(Stroke("AO"))
		return  # strict rule.

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
		yield S((), State.stroke_start, False)
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

prefix_strokes: Dict[Stroke, Stroke]={Stroke(x): Stroke(y) for line in [
	"RAOE   RE     ",
	"PRAOE  PRE    ",
	"TPOR   TPAUR  ",
	"OPB    AUPB   ",
	"OR     AUR    ",
	"OUT    AOUT   ",
	] for x, y in [line.split()]}
suffix_strokes: Dict[Stroke, Stroke]={Stroke(x): Stroke(y) for line in [
		"ER      *ER     ",
		"ERS     *ERS    ",
		"ERD     *ERD    ",
		"OR      O*R     ",
		"ORS     O*RS    ",
		"ORD     O*RD    ",
		"EU      KWREU   ",  # (Plover theory) only if it's spelled with y? Not really. (cookie)
		"AOE     KWREU   ",
		"EUS     KWREUS  ",  # IS is -is suffix while YIS is -ies (-y + -s) suffix...
		"AOES    KWREUS  ",
		"PHEPBT  *PLT    ",
		"KUL     K-L     ",
		"KULS    K-LS    ",
		"KAL     K-L     ",
		"KALS    K-LS    ",
		"AL      A*L     ",
		"ALS     A*L     ",
		"APB     A*PB    ",
		"APBS    A*PB    ",
		"OL      O*L     ",
		"OLS     O*L     ",
		"OPB     O*PB    ",
		"OPBS    O*PB    ",
		] for x, y in [line.split()]}
def fix_outline(x: Strokes)->Strokes:
	result: List[Stroke]=[]
	for s in x:
		if s in Stroke("-RPBLGTSDZ") and result and (result[-1]&right_half)==Stroke("-S"):
			result[-1]=result[-1]-Stroke("-S")+Stroke("-F")+s
		elif (s&Stroke("-FRPBLGTSDZ"))==Stroke("-SD"):
			result.append(s-Stroke("-S")+Stroke("-F"))
		elif result and s==Stroke("-S") and (result[-1]&Stroke("-DZ"))==Stroke("-D"):
			result[-1]+=Stroke("-Z")
		else:
			result.append(s)

	i=len(result)
	while i>1 and result[i-1] in suffix_strokes:
		i-=1
	result=result[:i]+[suffix_strokes[a] for a in result[i:]]
	# (it's not possible for the whole word to consist of all prefixes or suffixes

	i=0
	while i<len(result)-1 and result[i] in prefix_strokes:
		i+=1
	result=[prefix_strokes[a] for a in result[:i]]+result[i:]

	return tuple(result)

def generate_fixed(whole: Matches)->Tuple[Strokes, ...]:
	return tuple({
		fix_outline(x.strokes): None
		for x in generate_complete(whole)
		})  # to remove duplicates
	# dict to remove duplicates
	
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
