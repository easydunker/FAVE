# FAVE
Modified FAVE

This is a modified version of FAVE aligner for mandarin from https://web.sas.upenn.edu/phonetics-lab/facilities

This aligner takes a input file with [start_time, end_time, transcription] entries and outputs a TextGrid format file, which could be used by Praat.

`./loop.sh [dir]` is a utility script that will process all files in directory [dir]. Files should be in (a.wav, a.txt) pairs. The name of the .wav file must match with corresponding .txt file.
.txt files should contain [start_time, end_time, transcription].
