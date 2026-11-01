"""
Unit Tests for Non-AI Musical Analysis (Chroma, Chords, Key, Tempo)
"""
import numpy as np
from workers.arrangement.music_analyzer import MusicAnalyzer


def test_key_estimation_c_major():
    analyzer = MusicAnalyzer()

    # Synthetic chroma with strong C Major profile (C=0, E=4, G=7)
    chroma = np.zeros((12, 10))
    chroma[0, :] = 1.0  # C
    chroma[4, :] = 0.8  # E
    chroma[7, :] = 0.9  # G
    chroma[2, :] = 0.3  # D
    chroma[9, :] = 0.3  # A

    key_event = analyzer._estimate_key(chroma)
    assert key_event.key in ("C", "G", "F")  # Closest major keys in circle of fifths
    assert key_event.mode == "major"


def test_chord_estimation():
    analyzer = MusicAnalyzer()

    # Chroma with distinct C Major triad in first 2 seconds, G Major in next 2 seconds
    chroma = np.zeros((12, 40))
    # First 20 frames = C Major (C, E, G)
    chroma[0, :20] = 1.0
    chroma[4, :20] = 0.8
    chroma[7, :20] = 0.9

    # Next 20 frames = G Major (G=7, B=11, D=2)
    chroma[7, 20:] = 1.0
    chroma[11, 20:] = 0.8
    chroma[2, 20:] = 0.9

    chords = analyzer._estimate_chords(chroma, duration=4.0)

    assert len(chords) >= 1
    symbols = [c.symbol for c in chords]
    assert any("C" in s for s in symbols)

