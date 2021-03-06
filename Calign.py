#!/usr/bin/python
# encoding: utf-8

""" Usage:
      Calign.py [options] wavfile trsfile output_file
      where options may include:
          -r sampling_rate -- override which sampling rate model to use, either 8000 or 16000
          -a user_supplied_dictionary -- encoded in utf8, the dictionary will be combined with the dictionary in the model
          -d user_supplied_dictionary -- encoded in utf8, the dictionary will be used alone, NOT combined with the dictionary in the model
          -p punctuations -- encoded in utf8, punctuations and other symbols in this file will be deleted in forced alignment, the default is to use "puncs" in the model
          -y include_pinyin
"""

import os
import sys
import getopt
import wave
import codecs
import io
import subprocess

HOMEDIR = '.'
MODEL_DIR = HOMEDIR + '/model'

missing = io.open('MissingWords', 'w', encoding='utf8')
sr_models = None

def prep_mlf(trsfile, tmpbase):

    f = codecs.open(tmpbase + '.dict', 'r', 'utf-8')
    lines = f.readlines()
    f.close()
    dict = []
    for line in lines:
        dict.append(line.split()[0])
    f = codecs.open(tmpbase + '.puncs', 'r', 'utf-8')
    lines = f.readlines()
    f.close()
    puncs = []
    for line in lines:
        puncs.append(line.strip())

    f = codecs.open(trsfile, 'r', 'utf-8')
    lines = f.readlines()
    f.close()

    fw = codecs.open(tmpbase + '.mlf', 'w', 'utf-8')
    fw.write('#!MLF!#\n')
    fw.write('"' + tmpbase + '.lab"\n')
    fw.write('sp\n')
    i = 0
    unks = set()
    while (i < len(lines)):
        txt = lines[i].replace('\n', '')
        txt = txt.replace('{breath}', 'br').replace('{noise}', 'ns')
        txt = txt.replace('{laugh}', 'lg').replace('{laughter}', 'lg')
        txt = txt.replace('{cough}', 'cg').replace('{lipsmack}', 'ls')
        for pun in puncs:
            txt = txt.replace(pun,  '')
        for wrd in txt.split():
            if (wrd in dict):
                fw.write(wrd + '\n')
                fw.write('sp\n')
            else:
                unks.add(wrd)
        i += 1
    fw.write('.\n')
    fw.close()
    return unks


def gen_res(infile1, infile2, outfile):
    
    f = codecs.open(infile1, 'r', 'utf-8')
    lines = f.readlines()
    f.close()
    if len(lines) < 2:
        return False
    
    f = codecs.open(infile2, 'r', 'utf-8')
    lines2 = f.readlines()
    f.close()
    words = []
    for line in lines2[2:-1]:
        if (line.strip() <> 'sp'):
            words.append(line.strip())
    words.reverse()

    fw = codecs.open(outfile, 'w', 'utf-8')
    fw.write(lines[0])
    fw.write(lines[1])
    for line in lines[2:-1]:
        if ((line.split()[-1].strip() == 'sp') or (len(line.split()) <> 5)):
            fw.write(line)
        else:
            fw.write(line.split()[0] + ' ' + line.split()[1] + ' ' + line.split()[2] + ' ' + line.split()[3] + ' ' + words.pop() + '\n')
    fw.write(lines[-1])
    return True

def getopt2(name, opts, default = None) :
        value = [v for n,v in opts if n==name]
        if len(value) == 0 :
                return default
        return value[0]


def readAlignedMLF(mlffile, SR, wave_start):
    # This reads a MLFalignment output  file with phone and word
    # alignments and returns a list of words, each word is a list containing
    # the word label followed by the phones, each phone is a tuple
    # (phone, start_time, end_time) with times in seconds.

    f = open(mlffile, 'r')
    lines = [l.rstrip() for l in f.readlines()]
    f.close()

    if len(lines) < 3:
        raise ValueError("Alignment did not complete succesfully.")

    j = 2
    ret = []
    while (lines[j] <> '.'):
        if (len(lines[j].split()) == 5):  # Is this the start of a word; do we have a word label?
            # Make a new word list in ret and put the word label at the beginning
            wrd = lines[j].split()[4]
            ret.append([wrd])

        # Append this phone to the latest word (sub-)list
        ph = lines[j].split()[2]
        if (SR == 11025):
            st = (float(lines[j].split()[0]) / 10000000.0 + 0.0125) * (11000.0 / 11025.0)
            en = (float(lines[j].split()[1]) / 10000000.0 + 0.0125) * (11000.0 / 11025.0)
        else:
            st = float(lines[j].split()[0]) / 10000000.0 + 0.0125
            en = float(lines[j].split()[1]) / 10000000.0 + 0.0125
        if st < en:
            ret[-1].append([ph, st + wave_start, en + wave_start])

        j += 1

    return ret


def writeTextGrid(outfile, word_alignments, pinyin, tmpbase, pinyins):
    include_pinyin = False
    if pinyin:
        include_pinyin = bool(pinyin)

    # make the list of just phone alignments
    phons = []
    for wrd in word_alignments:
        phons.extend(wrd[1:])  # skip the word label

    # make the list of just word alignments
    # we're getting elements of the form:
    #   ["word label", ["phone1", start, end], ["phone2", start, end], ...]
    wrds = []
    # pinyinwrds = ""
    # pinyinwrds_cnt = 0
    idx_pinyin = 0
    for wrd in word_alignments:
        # If no phones make up this word, then it was an optional word
        # like a pause that wasn't actually realized.
        if len(wrd) == 1:
            continue
        if include_pinyin and wrd[0] != "sp":
            if idx_pinyin >= len(pinyins):
                print "Pinyin and alignment does not match"
                return
            wrds.append([wrd[0], wrd[1][1], wrd[-1][2], pinyins[idx_pinyin]])
            idx_pinyin += 1
        else:
            wrds.append([wrd[0], wrd[1][1], wrd[-1][2]])  # word label, first phone start time, last phone end time

    # if include_pinyin is True:
        # pinyinf = open(tmpbase + "-pinyin.txt", 'w')
        # pinyinf.write(pinyinwrds)
        # pinyinf.close()
        # cmd = "adso -y -f " + tmpbase + "-pinyin.txt" + "|sed 's/[1-9]/& /g' >" + tmpbase + "-pinyin.out"
        # os.system(cmd)
        # f = open(tmpbase + "-pinyin.out")
        # output = f.readline()
        # f.close()
        # pinyins = output.split()

    # write the phone interval tier
    fw = open(outfile, 'w')
    fw.write('File type = "ooTextFile short"\n')
    fw.write('"TextGrid"\n')
    fw.write('\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][2]) + '\n')
    fw.write('<exists>\n')
    if include_pinyin is True:
        fw.write('3\n')
    else:
        fw.write('2\n')
    fw.write('"IntervalTier"\n')
    fw.write('"phone"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(phons)) + '\n')
    for k in range(len(phons)):
        fw.write(str(phons[k][1]) + '\n')
        fw.write(str(phons[k][2]) + '\n')
        fw.write('"' + phons[k][0] + '"' + '\n')

    if include_pinyin is True:
        # write the pinyin interval tier
        fw.write('"IntervalTier"\n')
        fw.write('"pinyin"\n')
        fw.write(str(phons[0][1]) + '\n')
        fw.write(str(phons[-1][-1]) + '\n')
        fw.write(str(len(wrds)) + '\n')
        for k in range(len(wrds) - 1):
            fw.write(str(wrds[k][1]) + '\n')
            fw.write(str(wrds[k + 1][1]) + '\n')
            if wrds[k][0] != "sp":
                fw.write('"' + wrds[k][-1] + '"' + '\n')
            else:
                fw.write('"' + wrds[k][0] + '"' + '\n')

        fw.write(str(wrds[-1][1]) + '\n')
        fw.write(str(phons[-1][2]) + '\n')
        if wrds[-1][0] != "sp":
            fw.write('"' + wrds[-1][-1] + '"' + '\n')
        else:
            fw.write('"' + wrds[-1][0] + '"' + '\n')

    # write the word interval tier
    fw.write('"IntervalTier"\n')
    fw.write('"word"\n')
    fw.write(str(phons[0][1]) + '\n')
    fw.write(str(phons[-1][-1]) + '\n')
    fw.write(str(len(wrds)) + '\n')
    for k in range(len(wrds) - 1):
        fw.write(str(wrds[k][1]) + '\n')
        fw.write(str(wrds[k + 1][1]) + '\n')
        fw.write('"' + wrds[k][0] + '"' + '\n')

    fw.write(str(wrds[-1][1]) + '\n')
    fw.write(str(phons[-1][2]) + '\n')
    fw.write('"' + wrds[-1][0] + '"' + '\n')

    fw.close()


def prep_wav(orig_wav, out_wav, sr_override, wave_start, wave_end):
    global sr_models

    if os.path.exists(out_wav) and False:
        f = wave.open(out_wav, 'r')
        SR = f.getframerate()
        f.close()
        print "Already re-sampled the wav file to " + str(SR)
        return SR

    f = wave.open(orig_wav, 'r')
    SR = f.getframerate()
    f.close()

    soxopts = ""
    if float(wave_start) != 0.0 or wave_end != None:
        soxopts += " trim " + wave_start
        if wave_end != None:
            soxopts += " " + str(float(wave_end) - float(wave_start))

    if (sr_models != None and SR not in sr_models) or (sr_override != None and SR != sr_override) or soxopts != "":
        new_sr = 11025
        if sr_override != None:
            new_sr = sr_override

        print "Resampling wav file from " + str(SR) + " to " + str(new_sr) + soxopts + "..."
        SR = new_sr
        os.system("sox " + orig_wav + " -r " + str(SR) + " " + out_wav + soxopts)
    else:
        # print "Using wav file, already at sampling rate " + str(SR) + "."
        os.system("cp -f " + orig_wav + " " + out_wav)

    return SR

def processOneSegment(lines, tmpbase, lineNumber, SR, dict, puncs, pinyin):
    if len(lines[lineNumber].split("\t")) != 3:
        print "Bad transcription line: " + lines[lineNumber]
        return
    wavestart = lines[lineNumber].split("\t")[0]
    waveend = lines[lineNumber].split("\t")[1]
    line = lines[lineNumber].split("\t")[2]

    include_pinyin = False
    if pinyin:
        include_pinyin = bool(pinyin)

    base = tmpbase + '-' + str(lineNumber)
    spacedLine = line.replace('', ' ')

    prep_wav(tmpbase + '.wav', base + '.wav', SR, wavestart, waveend)

    # prepare plpfile
    os.system('HCopy -C ' + MODEL_DIR + '/' + str(SR) + '/config ' + base + '.wav ' + base + '.plp')
    unks = prep_mlf_in_mem(spacedLine, dict, puncs, base)
    for unk in unks:
        missing.write(u'Missing: ' + unk + '\n')

    # run alignment
    os.system('HVite -T 1 -a -m -t 10000.0 10000.0 100000.0 -I ' + base + '.mlf -H ' +
              MODEL_DIR + '/' + str(SR) + '/macros -H ' + MODEL_DIR + '/' + str(SR) + '/hmmdefs -i ' + base + '.aligned' + ' ' +
              tmpbase + '.dict ' + MODEL_DIR + '/monophones ' + base + '.plp' + ' > ' + base + '.results')

    success = gen_res(base + '.aligned', base + '.mlf', base + '.results.mlf')
    if success:
        word_alignments = readAlignedMLF(base + '.results.mlf', SR, float(wavestart))
        wrds = ""
        wrd_cnt = 0
        for wrd in word_alignments:
            if wrd[0] != "sp":
                wrds += wrd[0]
                wrd_cnt += 1
        if include_pinyin is True:
            pinyinf = open(base + "-pinyin.txt", 'w')
            print wrds
            pinyinf.write(wrds)
            pinyinf.close()
            cmd = "adso -y -f " + base + "-pinyin.txt" + "|sed 's/[1-9]/& /g' >" + base + "-pinyin.out"
            ok = os.system(cmd)
            os.system("rm -f " + base + "-pinyin.txt")
            if ok != 0:
                print "Ignoring line as adso generates bad character with line: " + lines[lineNumber]
                return None, None

            tmpf = open(base + "-pinyin.out")
            pinyin = tmpf.readline().split()
            os.system("rm -f " + base + "-pinyin.out")
            if len(pinyin) != wrd_cnt:
                print "Ignoring line as pinyin length does not match with Hanzi length: " + lines[lineNumber]
                return None, None
            return word_alignments, pinyin
        else:
            return word_alignments, None
    else:
        print "Aligning failed for " + lines[lineNumber]
        return None, None

def prep_mlf_in_mem(txt, dict, puncs, base):

    fw1 = codecs.open(base + '.mlf', 'w', 'utf-8')
    fw1.write('#!MLF!#\n')
    fw1.write('"' + base + '.lab"\n')
    fw1.write('sp\n')
    unks = set()
    txt = txt.replace('{breath}', 'br').replace('{noise}', 'ns')
    txt = txt.replace('{laugh}', 'lg').replace('{laughter}', 'lg')
    txt = txt.replace('{cough}', 'cg').replace('{lipsmack}', 'ls')
    for pun in puncs:
        txt = txt.replace(pun,  '')
    for wrd in txt.split():
        if (wrd in dict):
            fw1.write(wrd + '\n')
            fw1.write('sp\n')
        else:
            unks.add(wrd)
    fw1.write('.\n')
    fw1.close()
    return unks


if __name__ == '__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:], "r:a:d:p:y:")

        # get the three mandatory arguments
        wavfile, trsfile, outfile = args
        # get options
        sr_override = getopt2("-r", opts)
        dict_add = getopt2("-a", opts)
        dict_alone = getopt2("-d", opts)
        puncs = getopt2("-p", opts)
        include_pinyin = getopt2("-y", opts, default=True)

    except:
        print __doc__
        sys.exit(0)

    tmpbase = '/tmp/' + os.environ['USER'] + '_' + str(os.getpid())
    
    #find sampling rate and prepare wavefile
    if sr_override:
        SR = int(sr_override)
        os.system('sox ' + wavfile + ' -r ' + str(SR) + ' ' + tmpbase + '.wav')
    else:
        f = wave.open(wavfile, 'r')
        SR = f.getframerate()
        f.close()
        if (SR not in [8000, 16000]):
            os.system('sox ' + wavfile + ' -r 16000 ' + tmpbase + '.wav')
            SR = 16000
        else:
            os.system('cp -f ' + wavfile + ' ' + tmpbase + '.wav') 
 
    #prepare plpfile
    os.system('HCopy -C ' + MODEL_DIR + '/' + str(SR) + '/config ' + tmpbase + '.wav ' + tmpbase + '.plp')

    #prepare mlfile and dictionary
    if dict_alone:
        f = codecs.open(dict_alone, 'r', 'utf-8')
        lines = f.readlines()
        f.close()
        lines = lines + ['sp sp\n']
    else:
        f = codecs.open(MODEL_DIR + '/dict', 'r', 'utf-8')
        lines = f.readlines()
        f.close()
        if (dict_add):
            f = codecs.open(dict_add, 'r', 'utf-8')
            lines2 = f.readlines()
            f.close()
            lines = lines + lines2
    fw = codecs.open(tmpbase + '.dict', 'w', 'utf-8')
    for line in lines:
        fw.write(line)

    if puncs:
        os.system('cp -f ' + puncs + ' ' + tmpbase + '.puncs')
    else:
        os.system('cp -f ' + MODEL_DIR + '/puncs ' + tmpbase + '.puncs')

    #read dict
    f = codecs.open(tmpbase + '.dict', 'r', 'utf-8')
    lines = f.readlines()
    f.close()
    dict = []
    for line in lines:
        dict.append(line.split()[0])
    #read puncs
    f = codecs.open(tmpbase + '.puncs', 'r', 'utf-8')
    lines = f.readlines()
    f.close()
    puncs = []
    for line in lines:
        puncs.append(line.strip())
    #read input text
    f = codecs.open(trsfile, 'r', 'utf-8')
    lines = f.readlines()
    f.close()

    word_alignments = []
    pinyins = []
    i = 0
    while (i < len(lines)):
        r, pinyin = processOneSegment(lines, tmpbase, i, SR, dict, puncs, include_pinyin)
        if r is not None:
            word_alignments += r
        if pinyin is not None:
            pinyins.extend(pinyin)
        i += 1

    writeTextGrid(outfile, word_alignments, include_pinyin, tmpbase, pinyins)

    #clean up
    os.system('rm -f ' + tmpbase + '*')
