# backend/audio/waveform_processor.py
import numpy as np

def downsample(samples, factor):
    if factor <= 1:
        return samples
    return samples[::factor]

def smooth(samples, window):
    if window <= 1:
        return samples
    # trim to multiple of window
    trim_len = len(samples) - (len(samples) % window)
    arr = samples[:trim_len].reshape(-1, window).mean(axis=1)
    return arr
