# plover-generate
Generate a dictionary from a list of rules. Tailored for Plover theory.

### Additional files required to run the program

* `main.json`: Taken directly from Plover. Put it in the same directory as the scripts.
* `open-dict.txt`: Downloaded from [Open dict data](https://github.com/open-dict-data/ipa-dict).
* `frequency-list`: Any frequency list can be used.

   Each line must have the format `<word><tab-character><frequency>` where:

   * `<word>` is the word. (must not contain a tab character)
   * `<tab-character>` is a tab character.
   * `<frequency>` is a real number.

   Can be downloaded from [Wiktionary](https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/PG/2006/04/1-10000) for example.

   It's possible to use an empty file, however uncommon words may take the outline instead of more common words.

### To generate a dictionary

Usually you would only need to run

    python3 main2.py
    python3 main3.py -g

Run `python3 main3.py --help` to see what's the default output path. Can be changed with `-o`/`--output` flag.

Most other files have either documentation at the top of the file, or otherwise (if they're executable)
run them with `--help` flag to read the documentation.

### Tips

* The programs are also compatible with `pypy3`. It's also possible to pass `-OO` flag to `pypy3` to
disable assertions to speed up the programs.
* It's possible to run `main3.py -g -o a.json && cp a.json b.json` and load `b.json`
into Plover, so that it's possible to use a dictionary while waiting for the new dictionary to be
generated.

### Testing

It's possible to preview the result of a rule modification on some words by running with
`--word-filter`. A typical run is (on Unix systems)

    python3 main3.py -o /dev/stdout --no-output-errors --word-filter word1,word2
