#!/usr/bin/env python3

from math import sin, pi, ceil, floor
import struct

ELEM_IN_WORD = 50  # 50 elements in 'PARIS '
QUIET_IN_WORD = 19
SND_IN_WORD = ELEM_IN_WORD - QUIET_IN_WORD
ELEMS_PER_DIT = 1
ELEMS_PER_DAH = 3
ELEMS_INTRA_CHAR = 1
ELEMS_INTER_CHAR = 3
ELEMS_INTER_WORD = 7

HARD_PUNC = ':()[]\'"@+'

MorseDef = {
    'A'   : '.-',
    'B'   : '-...',
    'C'   : '-.-.',
    'D'   : '-..',
    'E'   : '.',
    'F'   : '..-.',
    'G'   : '--.',
    'H'   : '....',
    'I'   : '..',
    'J'   : '.---',
    'K'   : '-.-',
    'L'   : '.-..',
    'M'   : '--',
    'N'   : '-.',
    'O'   : '---',
    'P'   : '.--.',
    'Q'   : '--.-',
    'R'   : '.-.',
    'S'   : '...',
    'T'   : '-',
    'U'   : '..-',
    'V'   : '...-',
    'W'   : '.--',
    'X'   : '-..-',
    'Y'   : '-.--',
    'Z'   : '--..',
    '0'   : '-----',
    '1'   : '.----',
    '2'   : '..---',
    '3'   : '...--',
    '4'   : '....-',
    '5'   : '.....',
    '6'   : '-....',
    '7'   : '--...',
    '8'   : '---..',
    '9'   : '----.',
    '.'   : '.-.-.-',
    ','   : '--..--',
    '?'   : '..--..',
    '-'   : '-....-',
    '='   : '-...-',
# encode forward and back slash to same pattern
    '/'   : '-..-.',
    '\\'  : '-..-.',
# end slashes
    ':'   : '---...',
    '('   : '-.--.', # ITU-R M.1677-1 says this is open paren but same as <KN>
    ')'   : '-.--.-',
# square brackets as parens
    '['   : '-.--.', # see open paren comment
    ']'   : '-.--.-',
# end brackets
    '\''  : '.----.',
    '"'   : '.-..-.',
    '@'   : '.--.-.',
    '+'   : '.-.-.',
# prosigns here but not implemented
    'AA'  : '.-.-',
    'AR'  : '.-.-.',
    'AS'  : '.-...',
    'BK'  : '-...-.-',
    'BT'  : '-...-',
    'CL'  : '-.-..-..',
    'CT'  : '-.-.-',
    'DO'  : '-..---',
    'KN'  : '-.--.',
    'SK'  : '...-.-',
    'SN'  : '...-.',
    'SOS' : '...---...',
}

class TextSanitizer:

    def __init__(self, readable, no_hard_punc = False):
        self._src = readable
        self._hard_punc = not no_hard_punc # ignore "hard" punctuation

    def __iter__(self):
        return self

    def __next__(self):
        chrs = []
        c = self._src.read(1)
        while c:
            if c.upper() in MorseDef: # valid morse char
                if self._hard_punc or c not in HARD_PUNC: # check if we are allowing hard punctuation
                    chrs.append(c.upper())
            elif not c.strip(): # c is whitespace
                if chrs: break # break if we have characters otherwise keep scanning
            c = self._src.read(1)
        if chrs:
            return ''.join(chrs)
        else:
            raise StopIteration

def sanitize_text(txt, no_hard_punc = False):
    '''Remove extra whitespace and unrecognized characters in text'''
    ts = TextSanitizer(text, no_hard_punc)
    return ' '.join(iter(ts))

class CodeRender():

    def __init__(self, freq, wpm, chr_wpm=None, output_hz=44100, output_bits=16, taper=0.2):
        if output_bits != 16: raise NotImplementedError('We only support 16-bit signed output')
        self._sample_rate = output_hz
        self._output_bits = output_bits
        self._maxv = int((2**(output_bits - 1) - 1) * .9) # signed output

        if not chr_wpm: chr_wpm = wpm
        chr_elem_dur = 60 / (ELEM_IN_WORD * chr_wpm) # get sound element in seconds
        self.chr_elem_dur = chr_elem_dur
        wrd_elem_dur = 60 / (QUIET_IN_WORD * wpm) - SND_IN_WORD / QUIET_IN_WORD * chr_elem_dur

        taper_dur = taper * chr_elem_dur

        self.dit = self.mksnd(freq, chr_elem_dur * ELEMS_PER_DIT, taper_dur)
        self.dah = self.mksnd(freq, chr_elem_dur * ELEMS_PER_DAH, taper_dur)
        print(chr_elem_dur * ELEMS_PER_DIT, chr_elem_dur * ELEMS_PER_DAH)
        print(len(self.dit), len(self.dah))
        self.intra_chr = self.mkquiet(chr_elem_dur * ELEMS_INTRA_CHAR)
        self.inter_chr = self.mkquiet(wrd_elem_dur * (ELEMS_INTER_CHAR - ELEMS_INTRA_CHAR))
        self.inter_wrd = self.mkquiet(wrd_elem_dur * (ELEMS_INTER_WORD - ELEMS_INTRA_CHAR))

    def mksnd(self, freq, dur, taper_dur=0):
        '''Make a normalized floating point array for a sound a freq for dur
           seconds at sample rate and ramp magnitude over taper_dur start and end'''

        from blim_sig import bandwidth_limit
        on_dur = self._sample_rate * dur
        elem_dur = self._sample_rate * self.chr_elem_dur
        data_base = [0.0] * ceil(elem_dur/2) + \
                    [1.0] * ceil(on_dur) + \
                    [0.0] * ceil(elem_dur/2)
        data = bandwidth_limit(data_base, self._sample_rate, 15, flen=int(elem_dur * ELEMS_PER_DIT))
        #from pylab import plot,show
        #plot(data)
        #show()
        sample_period = 1.0/self._sample_rate

        for idx in range(len(data)):
            data[idx] = int(data[idx] * self._maxv * sin(2 * pi * freq * sample_period * idx))

        return self.pack(data)

    def mkquiet(self, dur):
        return self.pack([0] * ceil(self._sample_rate * dur))

    def render(self, txt):
        for c in txt:
            if c not in MorseDef and c != ' ':
                raise ValueError('Text contains invalid morse character: "{}"'.format(c))
        output = []
        first = True # flag for first letter of word
        for c in txt:
            morse = MorseDef.get(c,' ')
            if morse == ' ':
                output.append(self.inter_wrd)
                first = True
            else:
                if not first: output.append(self.inter_chr)
                first = False
                last = len(morse)-1
                for idx, m in enumerate(morse):
                    if m == '.':
                        output.append(self.dit)
                    elif m == '-':
                        output.append(self.dah)
                    else: raise RuntimeError('This should never happen')
        return b''.join(output)

    def pack(self, values):
        return struct.pack('<'+'h'*len(values), *values)

if __name__ == '__main__':
    import argparse
    import os
    import subprocess
    import sys
    import wave

    parser = argparse.ArgumentParser(description='Turn text into morse code')
    parser.add_argument('-t','--tone',default=500,type=int,help='CW tone in Hz')
    parser.add_argument('-s','--speed',default=20,type=float,
                        help='Overall acheived CW word speed in WPM')
    parser.add_argument('-c','--char-speed',default=None,type=float,
                        help='CW character speed in WPM if different from overall speed')
    parser.add_argument('--skip',action='store_true',help='Skip hard punctuation in source file')
    parser.add_argument('--wav',action='store_true',help='Output a raw wave file instead of encoding ogg')
    parser.add_argument('-o','--output',default=None,help='Output file if default not desired')
    parser.add_argument('input', nargs='?', default=sys.stdin, type=argparse.FileType('r'),
                        help='Input text file (invalid chars ignored)')

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)


    args = parser.parse_args()

    if args.char_speed:
        if args.char_speed < 0:
            print('--char-speed must be a positive value')
            exit(1)
    if args.speed < 0:
        print('--speed must be a positive value')
        exit(1)
    if args.tone < 0:
        print('--tone must be a positive value')
        exit(1)
    if args.tone > 20000:
        print('--tone is too high frequency to render, try something < 20kHz')
        exit(1)
    if not args.output:
        if args.input != sys.stdin:
            args.output = os.path.splitext(args.input.name)[0] + ('.wav' if args.wav else '.ogg')
        else:
            print('You must specify --output when using stdin')
            exit(1)

    cr = CodeRender(freq = args.tone,
                    wpm = args.speed,
                    chr_wpm = args.char_speed)

    if args.wav:
        f = wave.open(args.output,'w')
        f.setframerate(44100)
        f.setnchannels(1)
        f.setsampwidth(2)
        write = lambda x: f.writeframes(x)
        close = lambda: f.close()
    else:
        sp = subprocess.Popen([
                'oggenc',
                '-o',args.output,
                '--raw-chan','1',
                '-q','10',
                '-'
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        write = lambda x: sp.stdin.write(x)
        def close():
            sp.stdin.close()
            sp.wait()

    for word in iter(TextSanitizer(args.input, args.skip)):
        write(cr.render(' ' + word))
    write(cr.render(' '))

    close()
