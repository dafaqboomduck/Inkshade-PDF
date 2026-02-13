"""
Narration pipeline orchestrator: PDF → analysis → script → audio → MP3.

Coordinates the full narration workflow:

1. **Layout detection** — render each page and run YOLO-based document
   layout analysis to identify titles, headings, body text, footnotes,
   page furniture, and other structural elements.
2. **Block classification** — match detected regions to text blocks
   extracted by PyMuPDF, then refine labels using typographic features.
3. **Script generation** — convert classified blocks into an ordered
   sequence of :class:`ReadingInstruction` objects with prosody
   annotations (pause durations, speed factors, skip flags).
4. **TTS synthesis** — synthesise each instruction to WAV audio via
   Piper TTS, respecting per-role speed factors.
5. **Audio assembly** — concatenate speech chunks and silence gaps,
   normalise volume, and export as MP3 or WAV.

Usage::

    from narration.pipeline import NarrationPipeline, NarrationConfig

    config = NarrationConfig(voice_name="en_US-lessac-medium")
    pipeline = NarrationPipeline(config)
    result = pipeline.narrate("input.pdf", "output.mp3")
    print(result.summary())
"""

import io
import logging
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple

from tqdm import tqdm

from narration.layout.classifier import classify_page
from narration.layout.detector import LayoutDetector
from narration.layout.feature_refiner import (
    detect_running_headers_footers,
    refine_classifications,
)
from narration.layout.models import ClassifiedBlock, LayoutLabel
from narration.script.models import ReadingInstruction, TextRole
from narration.script.reading_script import (
    build_document_script,
    build_page_script,
    preview_script,
)
from narration.tts.audio_builder import AudioBuilder
from narration.tts.engine import TTSEngine
from narration.tts.model_manager import ModelManager
from narration.utils.pdf_adapter import PDFAdapter

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Callbacks
# ------------------------------------------------------------------


@dataclass
class NarrationCallbacks:
    """Progress / cancellation callbacks for the narration pipeline."""

    on_phase: Optional[Callable[[str], None]] = None
    on_page: Optional[Callable[[int, int], None]] = None        # (current, total)
    on_segment: Optional[Callable[[int, int], None]] = None     # (current, total)
    on_cancelled: Optional[Callable[[], bool]] = None           # returns True if cancelled


# ------------------------------------------------------------------
# Page-level result
# ------------------------------------------------------------------


@dataclass
class PageNarrationResult:
    """Result for a single narrated page, yielded during streaming."""

    page_index: int
    wav_bytes: bytes
    instructions: List[ReadingInstruction] = field(default_factory=list)
    timing_offsets: List[Tuple[float, float, int]] = field(default_factory=list)
    word_count: int = 0
    duration_seconds: float = 0.0


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------


@dataclass
class NarrationConfig:
    """
    All tuneable parameters for the narration pipeline.

    Attributes:
        voice_name:            Piper voice identifier.
        voice_dir:             Override directory for cached voice models.
        yolo_model_path:       Path to YOLO ``.pt`` weights (``None`` for default).
        yolo_device:           Force YOLO device (``None`` for auto-select).
        yolo_confidence:       Minimum detection confidence.
        render_scale:          Resolution multiplier for page rendering.
        speed_multiplier:      Global speech speed scaling (stacks with per-role factors).
        pause_multiplier:      Global pause duration scaling.
        skip_footnotes:        Whether to skip footnote blocks.
        skip_captions:         Whether to skip caption blocks.
        strip_references:      Remove ``[N]``-style citation markers.
        announce_pages:        Insert "Page N" announcements between pages.
        page_transition_pause: Silence duration between pages (seconds).
        mp3_bitrate:           Bitrate string for MP3 export.
        normalize_dBFS:        Target loudness for volume normalisation.
        crossfade_ms:          Fade duration to smooth track boundaries.
        page_range:            ``(start, end)`` 0-based inclusive, or ``None`` for all.
        debug_layout_dir:      Save colour-coded layout images here (``None`` to skip).
        debug_script:          Print reading script and exit before synthesis.
        disable_tqdm:          Suppress progress bars.
    """

    voice_name: str = "en_US-lessac-medium"
    voice_dir: Optional[Path] = None

    yolo_model_path: Optional[str] = None
    yolo_device: Optional[str] = None
    yolo_confidence: float = 0.35
    render_scale: float = 1.5

    speed_multiplier: float = 1.0
    pause_multiplier: float = 1.0
    skip_footnotes: bool = True
    skip_captions: bool = False
    strip_references: bool = True
    announce_pages: bool = False
    page_transition_pause: float = 1.0

    mp3_bitrate: str = "192k"
    normalize_dBFS: float = -20.0
    crossfade_ms: int = 30

    page_range: Optional[Tuple[int, int]] = None

    debug_layout_dir: Optional[str] = None
    debug_script: bool = False
    disable_tqdm: bool = False


# ------------------------------------------------------------------
# Result
# ------------------------------------------------------------------


@dataclass
class NarrationResult:
    """
    Summary returned after narration completes.

    Captures per-phase timing, output metrics, and file info so the
    caller can report or log the results.
    """

    output_path: str = ""
    total_pages: int = 0
    pages_processed: int = 0
    total_instructions: int = 0
    spoken_instructions: int = 0
    skipped_blocks: int = 0
    word_count: int = 0
    audio_duration: float = 0.0
    file_size_mb: float = 0.0
    elapsed_seconds: float = 0.0

    time_layout: float = 0.0
    time_script: float = 0.0
    time_synthesis: float = 0.0
    time_export: float = 0.0

    def summary(self) -> str:
        """Format a human-readable summary of the narration run."""
        return (
            f"{'=' * 60}\n"
            f"NARRATION COMPLETE\n"
            f"{'=' * 60}\n"
            f"  Output:       {self.output_path}\n"
            f"  Pages:        {self.pages_processed} / {self.total_pages}\n"
            f"  Instructions: {self.spoken_instructions} spoken, "
            f"{self.skipped_blocks} skipped\n"
            f"  Words:        ~{self.word_count}\n"
            f"  Duration:     {self.audio_duration:.1f}s "
            f"({self.audio_duration / 60:.1f} min)\n"
            f"  File size:    {self.file_size_mb:.1f} MB\n"
            f"\n"
            f"  Layout detection: {self.time_layout:.1f}s\n"
            f"  Script building:  {self.time_script:.2f}s\n"
            f"  TTS synthesis:    {self.time_synthesis:.1f}s\n"
            f"  Audio export:     {self.time_export:.2f}s\n"
            f"  Total wall time:  {self.elapsed_seconds:.1f}s\n"
            f"{'=' * 60}"
        )


# ------------------------------------------------------------------
# Pipeline
# ------------------------------------------------------------------


class NarrationPipeline:
    """
    End-to-end PDF narration pipeline.

    Components (layout detector, TTS engine) are lazily initialised on
    first use, so debug-only runs that never reach synthesis avoid the
    overhead of loading voice models.
    """

    def __init__(self, config: Optional[NarrationConfig] = None):
        self.config = config or NarrationConfig()
        self._detector: Optional[LayoutDetector] = None
        self._engine: Optional[TTSEngine] = None
        self._model_mgr: Optional[ModelManager] = None

    # ------------------------------------------------------------------
    # Lazy component initialisation
    # ------------------------------------------------------------------

    def _ensure_detector(self) -> LayoutDetector:
        """Load the YOLO layout detector if not already initialised."""
        if self._detector is None:
            logger.info("Loading layout detector...")
            self._detector = LayoutDetector(
                model_path=self.config.yolo_model_path,
                device=self.config.yolo_device,
            )
            logger.info("Detector ready: %s", self._detector)
        return self._detector

    def _ensure_tts(self) -> TTSEngine:
        """Load the Piper TTS engine and download the voice if needed."""
        if self._engine is None:
            self._model_mgr = ModelManager(voice_dir=self.config.voice_dir)
            voice_path = self._model_mgr.ensure_voice_available(
                self.config.voice_name,
            )
            logger.info("Loading TTS engine: %s", self.config.voice_name)
            self._engine = TTSEngine(voice_path)
            logger.info("Engine ready: %s", self._engine)
        return self._engine

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def narrate(self, pdf_path: str, output_path: str) -> NarrationResult:
        """
        Narrate a PDF document and export as audio.

        Runs the full four-phase pipeline: layout detection, script
        generation, TTS synthesis, and audio export.  If
        ``config.debug_script`` is set, exits after phase 2 with the
        reading script printed to the log.

        Args:
            pdf_path:    Path to the input PDF.
            output_path: Destination file (``.mp3`` or ``.wav``).

        Returns:
            :class:`NarrationResult` with timing and output metrics.
        """
        t_total = time.perf_counter()
        cfg = self.config
        result = NarrationResult(output_path=output_path)
        is_wav = output_path.lower().endswith(".wav")

        # Use narrate_pages() internally and concatenate all page audio
        engine = self._ensure_tts()
        builder = AudioBuilder(sample_rate=engine.sample_rate)

        gen = self.narrate_pages(pdf_path)
        page_results: List[PageNarrationResult] = []
        final_result = None

        try:
            while True:
                page_result = next(gen)
                page_results.append(page_result)
                if page_result.wav_bytes and len(page_result.wav_bytes) > 44:
                    builder.add_speech(page_result.wav_bytes)
        except StopIteration as e:
            final_result = e.value

        if final_result is None:
            final_result = result

        final_result.output_path = output_path

        if cfg.debug_script:
            final_result.elapsed_seconds = time.perf_counter() - t_total
            return final_result

        # -- Phase 4: Post-processing & export --------------------------
        final_result = self._phase_export(builder, output_path, is_wav, final_result)

        final_result.elapsed_seconds = time.perf_counter() - t_total
        logger.info("\n%s", final_result.summary())
        return final_result

    # ------------------------------------------------------------------
    # Page-level streaming entry point
    # ------------------------------------------------------------------

    def narrate_pages(
        self,
        pdf_path: str,
        callbacks: Optional[NarrationCallbacks] = None,
    ) -> Generator[PageNarrationResult, None, NarrationResult]:
        """
        Yield per-page audio as each page completes.

        This is the streaming counterpart of :meth:`narrate`.  Instead
        of producing one monolithic audio file, it yields a
        :class:`PageNarrationResult` for every page as soon as layout
        detection, script building, and TTS synthesis finish for that
        page.

        Yields:
            :class:`PageNarrationResult` with ``page_index``,
            ``wav_bytes``, ``instructions``, ``timing_offsets``,
            ``word_count``, and ``duration_seconds``.

        Returns:
            Final :class:`NarrationResult` after all pages are done.
        """
        cb = callbacks or NarrationCallbacks()
        t_total = time.perf_counter()
        cfg = self.config
        result = NarrationResult()

        # --- Initialise components ------------------------------------
        if cb.on_phase:
            cb.on_phase("Loading layout detector")
        detector = self._ensure_detector()

        if cb.on_phase:
            cb.on_phase("Loading TTS engine")
        engine = self._ensure_tts()

        # --- Determine page range -------------------------------------
        if cb.on_phase:
            cb.on_phase("Layout detection")

        with PDFAdapter(pdf_path) as pdf:
            result.total_pages = pdf.page_count
            start = cfg.page_range[0] if cfg.page_range else 0
            end = cfg.page_range[1] if cfg.page_range else pdf.page_count - 1
            end = min(end, pdf.page_count - 1)
            page_indices = list(range(start, end + 1))
            total_pages = len(page_indices)

            all_classified: Dict[int, List[ClassifiedBlock]] = {}
            page_heights: Dict[int, float] = {}
            total_spoken = 0
            total_skipped = 0
            total_words = 0
            total_instructions = 0
            t_layout = 0.0
            t_script = 0.0
            t_synthesis = 0.0

            # --- Per-page loop ----------------------------------------
            for page_num, page_idx in enumerate(page_indices):
                # Check cancellation
                if cb.on_cancelled and cb.on_cancelled():
                    logger.info("Narration cancelled at page %d", page_idx)
                    break

                if cb.on_page:
                    cb.on_page(page_num, total_pages)

                # -- Phase 1: Layout for this page ---------------------
                t0 = time.perf_counter()
                classified, h = self._classify_single_page(
                    pdf, page_idx, detector
                )
                all_classified[page_idx] = classified
                page_heights[page_idx] = h
                t_layout += time.perf_counter() - t0

                if not classified:
                    # Yield empty result for pages with no text
                    yield PageNarrationResult(
                        page_index=page_idx,
                        wav_bytes=b"",
                    )
                    continue

                # -- Phase 2: Script for this page ---------------------
                t0 = time.perf_counter()
                page_script = build_page_script(
                    classified,
                    page_idx,
                    speed_multiplier=cfg.speed_multiplier,
                    pause_multiplier=cfg.pause_multiplier,
                    skip_footnotes=cfg.skip_footnotes,
                    skip_captions=cfg.skip_captions,
                    strip_references=cfg.strip_references,
                )
                t_script += time.perf_counter() - t0

                if not page_script:
                    yield PageNarrationResult(
                        page_index=page_idx,
                        wav_bytes=b"",
                    )
                    continue

                if cb.on_phase:
                    cb.on_phase(f"Synthesising page {page_idx + 1}")

                # -- Phase 3: TTS for this page ------------------------
                t0 = time.perf_counter()
                page_builder = AudioBuilder(sample_rate=engine.sample_rate)
                speakable = [inst for inst in page_script if not inst.should_skip]
                timing_offsets: List[Tuple[float, float, int]] = []
                cumulative_ms: float = 0.0
                spoken = 0
                skipped = 0
                page_words = 0

                for seg_idx, inst in enumerate(speakable):
                    if cb.on_cancelled and cb.on_cancelled():
                        break

                    if cb.on_segment:
                        cb.on_segment(seg_idx, len(speakable))

                    p = inst.prosody

                    # Silence before
                    if p.pause_before > 0:
                        silence_ms = p.pause_before * 1000
                        page_builder.add_silence(p.pause_before)
                        cumulative_ms += silence_ms

                    # Synthesise speech
                    start_ms = cumulative_ms
                    if inst.text:
                        try:
                            wav = engine.synthesize(
                                inst.text, speed_factor=p.speed_factor
                            )
                            page_builder.add_speech(wav)
                            dur = engine.get_audio_duration(wav)
                            cumulative_ms += dur * 1000
                            spoken += 1
                            page_words += len(inst.text.split())
                        except Exception as e:
                            logger.warning(
                                "TTS failed on page %d segment: %s", page_idx, e
                            )
                            skipped += 1
                            continue

                    end_ms = cumulative_ms

                    # Silence after
                    if p.pause_after > 0:
                        silence_ms = p.pause_after * 1000
                        page_builder.add_silence(p.pause_after)
                        cumulative_ms += silence_ms

                    timing_offsets.append((start_ms, end_ms, seg_idx))

                t_synthesis += time.perf_counter() - t0

                # -- Collect page audio --------------------------------
                total_spoken += spoken
                total_skipped += skipped
                total_words += page_words
                total_instructions += len(page_script)
                page_duration = page_builder.get_duration()

                # Export page audio to WAV bytes
                if page_builder.is_empty:
                    page_wav = b""
                else:
                    page_wav = self._builder_to_wav_bytes(page_builder)

                yield PageNarrationResult(
                    page_index=page_idx,
                    wav_bytes=page_wav,
                    instructions=page_script,
                    timing_offsets=timing_offsets,
                    word_count=page_words,
                    duration_seconds=page_duration,
                )

        # --- Finalise result ------------------------------------------
        result.pages_processed = len(page_indices)
        result.total_instructions = total_instructions
        result.spoken_instructions = total_spoken
        result.skipped_blocks = total_skipped
        result.word_count = total_words
        result.time_layout = t_layout
        result.time_script = t_script
        result.time_synthesis = t_synthesis
        result.elapsed_seconds = time.perf_counter() - t_total

        logger.info(
            "Page streaming complete: %d pages, %d spoken, %d skipped",
            result.pages_processed,
            total_spoken,
            total_skipped,
        )
        return result

    @staticmethod
    def _builder_to_wav_bytes(builder: AudioBuilder) -> bytes:
        """Export an AudioBuilder's content to in-memory WAV bytes."""
        import tempfile
        import os

        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            builder.export_wav(tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Phase 1 — Layout detection
    # ------------------------------------------------------------------

    def _phase_layout(
        self,
        pdf_path: str,
        detector: LayoutDetector,
        result: NarrationResult,
    ) -> Tuple[Dict[int, List[ClassifiedBlock]], Dict[int, float], NarrationResult]:
        """
        Render each page, run YOLO detection, match to text blocks,
        and refine with typographic features.

        Returns:
            ``(all_classified, page_heights, result)`` — the classified
            blocks dict, per-page heights, and the updated result.
        """
        cfg = self.config
        t0 = time.perf_counter()
        logger.info("Phase 1: Layout detection & classification")

        all_classified: Dict[int, List[ClassifiedBlock]] = {}
        page_heights: Dict[int, float] = {}

        with PDFAdapter(pdf_path) as pdf:
            result.total_pages = pdf.page_count
            start = cfg.page_range[0] if cfg.page_range else 0
            end = cfg.page_range[1] if cfg.page_range else pdf.page_count - 1
            end = min(end, pdf.page_count - 1)
            page_indices = range(start, end + 1)

            pbar = tqdm(
                page_indices,
                desc="Detecting layout",
                unit="page",
                disable=cfg.disable_tqdm,
            )
            for idx in pbar:
                pbar.set_postfix(page=f"{idx + 1}/{pdf.page_count}")
                classified, h = self._classify_single_page(
                    pdf,
                    idx,
                    detector,
                )
                all_classified[idx] = classified
                page_heights[idx] = h

            if len(all_classified) >= 3:
                detect_running_headers_footers(all_classified, page_heights)
                logger.debug("Running header/footer detection applied")

            if cfg.debug_layout_dir:
                _save_debug_layouts(
                    pdf, all_classified, cfg.render_scale, cfg.debug_layout_dir
                )

        result.pages_processed = end - start + 1
        result.time_layout = time.perf_counter() - t0
        logger.info(
            "Layout complete: %d pages in %.1fs",
            result.pages_processed,
            result.time_layout,
        )
        return all_classified, page_heights, result

    def _classify_single_page(
        self,
        pdf: PDFAdapter,
        page_index: int,
        detector: LayoutDetector,
    ) -> Tuple[List[ClassifiedBlock], float]:
        """
        Classify a single page with YOLO, falling back to feature-only
        classification on failure.

        Returns:
            ``(classified_blocks, page_height)``
        """
        cfg = self.config
        w, h = pdf.dimensions(page_index)

        try:
            blocks = pdf.text_structure(page_index)
            if not blocks:
                logger.debug("Page %d: no extractable text, skipping", page_index)
                return [], h

            img = pdf.render(page_index, scale=cfg.render_scale)
            classified = classify_page(
                detector,
                img,
                blocks,
                w,
                h,
                scale=cfg.render_scale,
                confidence=cfg.yolo_confidence,
            )
            logger.debug("Page %d: %d blocks classified", page_index, len(classified))
            return classified, h

        except Exception as e:
            logger.warning(
                "YOLO failed on page %d (%s), falling back to feature-only",
                page_index,
                e,
            )
            return self._fallback_classify(pdf, page_index, w, h), h

    @staticmethod
    def _fallback_classify(
        pdf: PDFAdapter,
        page_index: int,
        page_width: float,
        page_height: float,
    ) -> List[ClassifiedBlock]:
        """Classify blocks using typographic features only (no YOLO)."""
        try:
            blocks = pdf.text_structure(page_index)
            classified = [
                ClassifiedBlock(block=b, label=LayoutLabel.UNKNOWN, confidence=0.0)
                for b in blocks
            ]
            refine_classifications(classified, page_width, page_height)
            return classified
        except Exception as e:
            logger.error("Fallback classification failed on page %d: %s", page_index, e)
            return []

    # ------------------------------------------------------------------
    # Phase 2 — Script generation
    # ------------------------------------------------------------------

    def _phase_script(
        self,
        all_classified: Dict[int, List[ClassifiedBlock]],
        result: NarrationResult,
    ) -> Tuple[List[ReadingInstruction], NarrationResult]:
        """
        Build the document reading script from classified blocks.

        Returns:
            ``(script, result)`` — the instruction list and updated result.
        """
        cfg = self.config
        t0 = time.perf_counter()
        logger.info("Phase 2: Building reading script")

        script = build_document_script(
            all_classified,
            speed_multiplier=cfg.speed_multiplier,
            pause_multiplier=cfg.pause_multiplier,
            skip_footnotes=cfg.skip_footnotes,
            skip_captions=cfg.skip_captions,
            strip_references=cfg.strip_references,
            announce_pages=cfg.announce_pages,
            page_transition_pause=cfg.page_transition_pause,
        )

        result.time_script = time.perf_counter() - t0
        result.total_instructions = len(script)
        result.spoken_instructions = sum(
            1 for s in script if not s.should_skip and s.text
        )
        result.word_count = sum(len(s.text.split()) for s in script if s.text)

        logger.info(
            "Script ready: %d instructions (%d spoken, ~%d words) in %.3fs",
            result.total_instructions,
            result.spoken_instructions,
            result.word_count,
            result.time_script,
        )
        return script, result

    # ------------------------------------------------------------------
    # Phase 3 — TTS synthesis
    # ------------------------------------------------------------------

    def _phase_synthesis(
        self,
        script: List[ReadingInstruction],
        engine: TTSEngine,
        builder: AudioBuilder,
        result: NarrationResult,
    ) -> NarrationResult:
        """
        Synthesise every instruction in the reading script and assemble
        speech chunks with silence gaps in the audio builder.

        Individual TTS failures are logged and skipped rather than
        aborting the entire run.

        Returns:
            Updated :class:`NarrationResult`.
        """
        cfg = self.config
        t0 = time.perf_counter()
        logger.info("Phase 3: TTS synthesis")

        spoken = 0
        skipped = 0
        current_page = -1

        speakable = [inst for inst in script if not inst.should_skip]

        pbar = tqdm(
            speakable,
            desc="Synthesising",
            unit="seg",
            disable=cfg.disable_tqdm,
        )
        for inst in pbar:
            if inst.page_index != current_page:
                current_page = inst.page_index
                pbar.set_postfix(page=current_page + 1)

            p = inst.prosody

            if p.pause_before > 0:
                builder.add_silence(p.pause_before)

            if inst.text:
                try:
                    wav = engine.synthesize(inst.text, speed_factor=p.speed_factor)
                    builder.add_speech(wav)
                    spoken += 1
                    dur = engine.get_audio_duration(wav)
                    logger.debug(
                        "[%s %.2fx] %.1fs | %s",
                        inst.role.name,
                        p.speed_factor,
                        dur,
                        inst.text[:65].replace("\n", " "),
                    )
                except Exception as e:
                    logger.warning("TTS failed, skipping segment: %s", e)
                    skipped += 1
                    continue

            if p.pause_after > 0:
                builder.add_silence(p.pause_after)

        result.time_synthesis = time.perf_counter() - t0
        result.skipped_blocks = skipped
        logger.info(
            "Synthesis complete: %d spoken, %d skipped in %.1fs",
            spoken,
            skipped,
            result.time_synthesis,
        )
        return result

    # ------------------------------------------------------------------
    # Phase 4 — Export
    # ------------------------------------------------------------------

    def _phase_export(
        self,
        builder: AudioBuilder,
        output_path: str,
        is_wav: bool,
        result: NarrationResult,
    ) -> NarrationResult:
        """
        Normalise, crossfade, and export the assembled audio.

        Returns:
            Updated :class:`NarrationResult` with duration and file size.
        """
        cfg = self.config
        t0 = time.perf_counter()
        logger.info("Phase 4: Post-processing & export")

        if builder.is_empty:
            logger.warning("No audio produced — nothing to export")
            return result

        builder.normalize(target_dBFS=cfg.normalize_dBFS)
        builder.apply_crossfade(ms=cfg.crossfade_ms)

        if is_wav:
            builder.export_wav(output_path)
        else:
            builder.export_mp3(output_path, bitrate=cfg.mp3_bitrate)

        result.time_export = time.perf_counter() - t0
        result.audio_duration = builder.get_duration()

        out = Path(output_path)
        if out.exists():
            result.file_size_mb = out.stat().st_size / (1024 * 1024)

        return result


# ------------------------------------------------------------------
# Debug helpers
# ------------------------------------------------------------------


def _save_debug_layouts(
    pdf: PDFAdapter,
    all_classified: Dict[int, List[ClassifiedBlock]],
    scale: float,
    output_dir: str,
) -> None:
    """
    Save colour-coded classification overlay images for visual review.

    Imports the drawing function from the test suite.  Logs a warning
    and returns silently if the import fails.
    """
    try:
        from tests.test_classifier import draw_classified_blocks
    except ImportError:
        logger.warning("Could not import debug drawing — skipping layout images")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for idx, classified in sorted(all_classified.items()):
        img = pdf.render(idx, scale=scale)
        annotated = draw_classified_blocks(img, classified, scale)
        path = out / f"page_{idx:03d}.png"
        annotated.save(str(path))
        logger.debug("Saved layout debug image: %s", path)

    logger.info("Layout debug images saved to %s/", out)
