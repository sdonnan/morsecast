#!/usr/bin/env python3

import numpy as np

def bandwidth_limit(sig, samp_rate, bw, flen=None):
    sig = np.array(sig)
    if flen == None:
        flen=len(sig)//2
    filt = mksinc(bw,samp_rate,flen)
    fsig = np.convolve(filt,sig)[flen//2:-flen//2]
    return [ float(x) for x in np.real(fsig) ]

def mksinc(bw, samp_rate, samples):
    T = 1.0/samp_rate
    N = samples
    idx = int(round(bw*T*N,0))
    sig = np.concatenate((np.ones(idx), np.zeros(N-2*idx), np.ones(idx)))
    fy = np.fft.ifft(sig)
    return np.fft.fftshift(fy)

if __name__=="__main__":

    from pylab import *
    samp_rate = 44100
    pulse_dur = 0.18

    pulse_samps = int(round(pulse_dur*samp_rate,0))
    off_samps = pulse_samps//2
    sig = np.concatenate((np.zeros(off_samps), np.ones(pulse_samps), np.zeros(off_samps)))

    FLEN=len(sig)//2
    filt = mksinc(10,samp_rate,FLEN)
    fsig = np.convolve(filt,sig)[FLEN//2:-FLEN//2]
    subplot(2,1,1)
    plot(sig)
    plot(fsig)
    subplot(2,1,2)

    N = len(fsig)
    T = 1.0/samp_rate
    yf = np.fft.fft(fsig)
    xf = np.linspace(0.0, 1.0/(2.0*T), N/2)
    plot(xf, 2.0/N * np.abs(yf[:N//2]))
    xlim([0,200])
    show()
