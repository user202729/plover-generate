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
    python3 main3.py --generate

Run `python3 main3.py --help` to see what's the default output path. Can be changed with `--output` flag.

Most other files have either documentation at the top of the file, or otherwise (if they're executable)
run them with `--help` flag to read the documentation.
