"""
Non-AI Lyric-to-Note Aligner.
Aligns speech-to-text words and syllables to transcribed vocal melody notes.
Handles:
- Word and syllable timing
- Syllable segmentation (vowel nuclei)
- Melisma (one syllable across multiple notes)
- Multi-syllable words
"""
import re
import uuid
from typing import List, Optional

from backend.app.stt.base import STTResult, STTWord
from shared.music_schema.arrangement import LyricEvent, NoteEvent, SyllableType


class LyricAligner:
    """Non-AI alignment component for vocal lyrics and melody notes."""

    def __init__(self, timing_tolerance_seconds: float = 0.35):
        self.tolerance = timing_tolerance_seconds

    def align(
        self,
        stt_result: STTResult,
        vocal_notes: List[NoteEvent],
    ) -> List[LyricEvent]:
        """
        Align STT recognized words/syllables to vocal note events.
        """
        if not stt_result.words or not vocal_notes:
            return []

        # Sort vocal notes chronologically
        sorted_notes = sorted(vocal_notes, key=lambda n: n.start_time)
        lyric_events: List[LyricEvent] = []

        # Break words into syllables
        expanded_syllables: List[tuple[str, SyllableType, float, float]] = []
        for word_obj in stt_result.words:
            sylls = self._syllabify(word_obj.word)
            if len(sylls) == 1:
                expanded_syllables.append((sylls[0], SyllableType.SINGLE, word_obj.start_time, word_obj.end_time))
            else:
                total_duration = max(0.1, word_obj.end_time - word_obj.start_time)
                step = total_duration / len(sylls)
                for idx, syll in enumerate(sylls):
                    s_type = (
                        SyllableType.BEGIN
                        if idx == 0
                        else (SyllableType.END if idx == len(sylls) - 1 else SyllableType.MIDDLE)
                    )
                    s_start = word_obj.start_time + idx * step
                    s_end = s_start + step
                    expanded_syllables.append((syll, s_type, s_start, s_end))

        note_idx = 0
        num_notes = len(sorted_notes)

        for text, syll_type, w_start, w_end in expanded_syllables:
            # Advance note_idx to the closest note in time
            best_note: Optional[NoteEvent] = None
            min_diff = float("inf")

            # Look in a window around note_idx
            search_start = max(0, note_idx - 2)
            search_end = min(num_notes, note_idx + 6)

            for i in range(search_start, search_end):
                candidate = sorted_notes[i]
                diff = abs(candidate.start_time - w_start)
                if diff < min_diff:
                    min_diff = diff
                    best_note = candidate
                    note_idx = i

            assigned_note_id = best_note.id if (best_note and min_diff <= self.tolerance) else None
            assigned_start = best_note.start_time if assigned_note_id else w_start
            assigned_duration = best_note.duration if assigned_note_id else (w_end - w_start)

            lyric_events.append(
                LyricEvent(
                    id=str(uuid.uuid4()),
                    text=text,
                    start_time=round(float(assigned_start), 3),
                    duration=round(float(assigned_duration), 3),
                    note_id=assigned_note_id,
                    syllable_type=syll_type,
                    confidence=0.9 if assigned_note_id else 0.6,
                )
            )

            # Advance pointer if note matched
            if assigned_note_id and note_idx < num_notes - 1:
                note_idx += 1

        return lyric_events

    def _syllabify(self, word: str) -> List[str]:
        """
        Rule-based English syllabification via vowel clusters.
        """
        clean_word = re.sub(r"[^\w]", "", word)
        if len(clean_word) <= 3:
            return [clean_word]

        vowels = "aeiouy"
        # Find vowel cluster positions
        clusters = [m.span() for m in re.finditer(r"[aeiouy]+", clean_word.lower())]

        if len(clusters) <= 1:
            return [clean_word]

        # Ignore silent trailing 'e'
        if clean_word.lower().endswith("e") and not clean_word.lower().endswith("le") and len(clusters) > 1:
            if clusters[-1][1] == len(clean_word):
                clusters.pop()

        if len(clusters) <= 1:
            return [clean_word]

        syllables: List[str] = []
        last_cut = 0

        for i in range(len(clusters) - 1):
            c1_end = clusters[i][1]
            c2_start = clusters[i + 1][0]
            consonant_len = c2_start - c1_end

            if consonant_len <= 1:
                cut = c1_end
            elif consonant_len == 2:
                cut = c1_end + 1
            else:
                cut = c1_end + (consonant_len // 2)

            syllables.append(clean_word[last_cut:cut])
            last_cut = cut

        syllables.append(clean_word[last_cut:])
        return [s for s in syllables if s]

