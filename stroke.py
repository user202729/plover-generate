from typing import List, Dict, Mapping, Optional, Sequence, Tuple, Set, Callable, Any, Iterable, Union, MutableMapping, Generic, TypeVar
from plover_stroke import BaseStroke  # type: ignore

ShortReplacementT=List[Tuple[
		"Stroke", #old_keys
		str, #new_key
		"Stroke" #exclude
		]]

def short_replacement_():
	result: ShortReplacementT=[]
	for data in [  # target no "-" => implicit_hyphen_keys
("#",	"#-"),

("SKWR",	"J-"),
("SR",	"V-"),
("S",	"S-"),
("TKPW",	"G-"),
("TPH",	"N-"),
("TK",	"D-"),
("TP",	"F-"),
("T",	"T-"),
("KWR",	"Y-"),
("KP",	"X-", "TWH"),
("KH",	"Ch-"),
("K",	"K-"),
("PH",	"M-",	"WR"),  # MR- is possible (marine) but is less common than PL-
# yes, pseudo steno -> steno conversion is lossy.
("PW",	"B-"),
("P",	"P-"),
("W",	"W-"),
("HR",	"L-"),
("H",	"H-"),
("R",	"R-"),

# can cross the star
("AOEU",	"II",	""),
("AOE",	"EE",	""),
("AOU",	"UU",	""),
("A-",	"A"),
("O",	"O"),
("EU",	"I"),
("E",	"E"),
("U",	"U"),
("*",	"*"),

("-FRPBLG",	"-Nch"),
("-FRPB",	"-Rch"),
("-FRP",	"-Mp"),
("-FP",	"-Ch",	"-RB"),
("-F",	"-F"),
("-RB",	"-ʃ",	"-FPG"),
("-R",	"-R"),
("-PBLG",	"-J"),
("-PL",	"-M"),
("-PB",	"-N"),
("-P",	"-P"),
("-BG",	"-K"),
("-B",	"-B"),
("-L",	"-L"),
("-GS",	"-ʃn"),
("-G",	"-G"),
("-T",	"-T"),
("-S",	"-S"),
("-D",	"-D"),
("-Z",	"-Z"),
]:
		if len(data)==2:
			old_keys, new_key=data  # no hyphen => implicit hyphen
			old_keys=Stroke(old_keys)
			assert old_keys
			exclude=Stroke(
					map(Stroke.KEYS.__getitem__,
					range(
						Stroke.KEYS.index(old_keys.first()),
						Stroke.KEYS.index(old_keys.last())+1
						)
					))&~old_keys
		else:
			old_keys, new_key, exclude=data
			old_keys=Stroke(old_keys)
			exclude=Stroke(exclude)
		assert not (exclude&old_keys)
		assert old_keys
		result.append((old_keys, new_key, exclude))
	return result





class Stroke(BaseStroke):
	def __repr__(self)->str:
		rest=self
		keys: List[str]=[]
		for old_keys, new_key, exclude in short_replacement:
			if (rest&old_keys)==old_keys and not (exclude&self):
				rest-=old_keys
				keys.append(new_key)

		assert not rest

		left = ''
		middle = ''
		right = ''
		for k in keys:
			l = k.replace('-', '')
			if k[0] == '-':
				right += l
			elif k[-1]=="-":
				left += l
			else:
				middle += l
		s = left
		if not middle and right:
			s += '-'
		else:
			s += middle
		s += right
		return s

	def __str__(self):
		return self.__repr__()

	def raw_str(self)->str:
		return super().__repr__()


Stroke.setup(
		#e.KEYS, e.IMPLICIT_HYPHEN_KEYS, e.NUMBER_KEY, e.NUMBERS
		
keys = (
    '#',
    'S-', 'T-', 'K-', 'P-', 'W-', 'H-', 'R-',
    'A-', 'O-',
    '*',
    '-E', '-U',
    '-F', '-R', '-P', '-B', '-L', '-G', '-T', '-S', '-D', '-Z',
),

implicit_hyphen_keys = ('A-', 'O-', '5-', '0-', '-E', '-U', '*'),

number_key = '#',

numbers = {
    'S-': '1-',
    'T-': '2-',
    'P-': '3-',
    'H-': '4-',
    'A-': '5-',
    'O-': '0-',
    '-F': '-6',
    '-P': '-7',
    '-L': '-8',
    '-T': '-9',
}
		)


star=Stroke("*")
not_star=~star  # int bit mask.
zero_stroke=Stroke()

short_replacement: ShortReplacementT=short_replacement_()
