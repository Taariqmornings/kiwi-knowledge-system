"""
RagService — retrieval over the existing SQLite FTS5 index.

Re-uses the `articles_fts` table that the search panel already queries.  No
embeddings, no external dependencies.  For typical natural-language questions
("what is photosynthesis?", "how do plants make food?") keyword overlap with
the indexed summaries is high enough that BM25 returns the right articles in
< 100 ms across hundreds of thousands of rows.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Small, hardcoded stopword list — keeps tokenization dependency-free.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "for",
    "on", "with", "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "those", "these", "it", "its", "do", "does", "did", "done",
    "i", "you", "he", "she", "they", "we", "what", "which", "who", "whom",
    "when", "where", "why", "how", "can", "could", "should", "would", "will",
    "shall", "may", "might", "must", "have", "has", "had", "having", "not",
    "no", "yes", "from", "by", "at", "about", "into", "out", "up", "down",
    "over", "under", "between", "any", "all", "some", "many", "much", "more",
    "most", "less", "least", "than", "then", "so", "such", "very", "just",
    "only", "also", "too", "tell", "me", "explain", "describe", "give",
    "show", "want", "know", "please", "thanks", "thank", "your", "yours",
    "mine", "ours", "their", "his", "her", "him", "them", "us", "our", "my",
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}")

# Words that signal the user is asking a procedural / explanatory question.
# When present, retrieval boosts results from documentation / tutorial /
# wiki archives over Q&A pages.
_PROCEDURAL_HINTS = re.compile(
    r"\b(how|what|why|explain|describe|tell|guide|tutorial|example|examples|definition|define)\b",
    re.IGNORECASE,
)
# Archive name patterns that look like authoritative documentation.
# Matches the start of a typical ZIM filename: devdocs_en_python_*, wiki*,
# docs.python.org_*, libretexts.org_*, freecodecamp_*, etc.
_DOCS_NAME_RE = re.compile(
    r"^(devdocs|docs[\.\-_]|wiki|mdn|tldr|cppreference|libretexts|"
    r"freecodecamp|gutenberg|appropedia|tonedear|zimgit|gnu|"
    r"openstax|teachers|nostarch|musescore)",
    re.IGNORECASE,
)

# Q&A archives — Stack Exchange and friends. Their titles often contain
# every keyword densely (which BM25 loves), but the BODY is usually a
# back-and-forth conversation rather than authoritative reference. We
# penalize them so docs/wiki rise to the top organically.
_QA_NAME_RE = re.compile(
    r"(stackexchange|stackoverflow|\.qa\.|_qa_|/qa/)",
    re.IGNORECASE,
)


@dataclass
class RagSource:
    n: int
    article_id: int
    archive_id: str
    title: str
    archive_title: str
    archive_name: str
    path: str
    summary: str
    score: float = 0.0  # adjusted rank (lower = more relevant)


class RagService:

    @staticmethod
    def extract_keywords(query: str, limit: int = 6) -> List[str]:
        """Lowercase, strip stopwords, dedupe, keep up to `limit` significant terms."""
        seen = set()
        kept = []
        for tok in _TOKEN_RE.findall(query.lower()):
            if tok in _STOPWORDS or tok in seen:
                continue
            seen.add(tok)
            kept.append(tok)
            if len(kept) >= limit:
                break
        return kept

    @staticmethod
    def _safe_fts_term(term: str) -> Optional[str]:
        """Quote a single FTS term to neutralize special characters."""
        clean = re.sub(r'[^a-zA-Z0-9_-]', '', term)
        return clean if len(clean) >= 2 else None

    # Per-archive cap when assembling the final source list — prevents a
    # single Q&A site from monopolising the top-k.
    MAX_PER_ARCHIVE = 2

    # BM25 returns NEGATIVE scores where MORE NEGATIVE = better. To boost a
    # document's apparent relevance we multiply by a number > 1, making the
    # score more negative. Multipliers < 1 would weaken the score.
    DOCS_BOOST_PROCEDURAL = 1.6   # docs/wiki on procedural questions
    DOCS_BOOST_DEFAULT    = 1.25  # docs/wiki on factual / lookup queries

    # Much stronger boost when a query term matches the archive NAME (e.g.
    # "python" matches devdocs_en_python). Those articles are the bullseye
    # for the question even if they don't repeat the language name in body.
    ARCHIVE_NAME_BOOST = 3.0
    # Additive bonus on top of the multiplier — guarantees a bullseye hit
    # always outranks generic Q&A noise even when the raw BM25 magnitude
    # is small (e.g. a short docs page whose summary contains only one
    # query term gets rank ~-3 instead of ~-20).
    ARCHIVE_NAME_BONUS = -25.0

    # Q&A archives weaken (BM25 negative * factor < 1 = less negative = worse).
    # On procedural questions the penalty is heavier — Q&A threads rarely
    # answer "how do I …" cleanly the way docs/tutorials do.
    QA_PENALTY_PROCEDURAL = 0.45
    QA_PENALTY_DEFAULT    = 0.65

    @classmethod
    def _looks_procedural(cls, query: str) -> bool:
        return bool(_PROCEDURAL_HINTS.search(query))

    @classmethod
    def _is_docs_archive(cls, archive_name: str) -> bool:
        return bool(_DOCS_NAME_RE.match(archive_name or ""))

    @classmethod
    def _is_qa_archive(cls, archive_name: str) -> bool:
        return bool(_QA_NAME_RE.search(archive_name or ""))

    @classmethod
    def _run_fts(
        cls,
        db: Session,
        fts_query: str,
        limit: int,
        archive_ids: Optional[List[str]] = None,
    ) -> list:
        """
        Execute one FTS query and return raw rows (no scoring tweaks).
        Optionally restrict to a specific set of archive IDs — this is how
        the "bullseye" pass narrows to e.g. Python-named archives when the
        user query mentions Python.
        """
        if archive_ids:
            from sqlalchemy import bindparam
            stmt = text("""
                SELECT a.id, a.archive_id, a.title, a.path, a.summary,
                       COALESCE(arc.title, arc.name) AS archive_title,
                       arc.name                       AS archive_name,
                       bm25(articles_fts)             AS rank
                FROM articles a
                JOIN articles_fts ON a.id = articles_fts.rowid
                JOIN archives arc ON a.archive_id = arc.id
                WHERE articles_fts MATCH :q
                  AND LENGTH(COALESCE(a.summary, '')) >= 60
                  AND a.archive_id IN :aids
                ORDER BY rank
                LIMIT :k
            """).bindparams(bindparam("aids", expanding=True))
            return db.execute(stmt, {"q": fts_query, "k": limit,
                                     "aids": list(archive_ids)}).all()
        return db.execute(text("""
            SELECT a.id, a.archive_id, a.title, a.path, a.summary,
                   COALESCE(arc.title, arc.name) AS archive_title,
                   arc.name                       AS archive_name,
                   bm25(articles_fts)             AS rank
            FROM articles a
            JOIN articles_fts ON a.id = articles_fts.rowid
            JOIN archives arc ON a.archive_id = arc.id
            WHERE articles_fts MATCH :q
              AND LENGTH(COALESCE(a.summary, '')) >= 60
            ORDER BY rank
            LIMIT :k
        """), {"q": fts_query, "k": limit}).all()

    @classmethod
    def _archives_matching_terms(
        cls, db: Session, terms: List[str],
    ) -> tuple[set[str], set[str]]:
        """
        For each query term, find archives whose `name` contains it.
        Returns (matching_archive_ids, terms_that_matched).

        Example: term "python" matches devdocs_en_python_2026-04.zim → that
        archive is in the bullseye pool, and "python" is recorded as a
        term that's already implied by the archive (so we drop it from
        the FTS body query when retrieving from that archive).
        """
        archive_ids: set[str] = set()
        matched_terms: set[str] = set()
        for t in terms:
            rows = db.execute(
                text("SELECT id FROM archives WHERE LOWER(name) LIKE :p"),
                {"p": f"%{t.lower()}%"},
            ).all()
            if rows:
                matched_terms.add(t)
                for r in rows:
                    archive_ids.add(r[0])
        return archive_ids, matched_terms

    @classmethod
    def retrieve(
        cls,
        db: Session,
        query: str,
        top_k: int = 8,
    ) -> List[RagSource]:
        """
        Hybrid retrieval:
          1. Try a strict AND query first — forces every keyword to appear,
             which is how authoritative docs are typically written.
          2. If that returns fewer than top_k/2 hits, augment with an OR
             query and merge, preferring AND hits.
          3. Apply a per-archive cap so a single Q&A site can't monopolise
             the result list.
          4. Boost documentation-style archives (devdocs / wikipedia / etc.)
             so they outrank Q&A pages, especially on procedural questions
             ("how to …", "what is …", "explain …").

        Returns up to top_k RagSource objects sorted by adjusted relevance.
        """
        keywords = cls.extract_keywords(query)
        terms = [t for t in (cls._safe_fts_term(k) for k in keywords) if t]
        if not terms:
            return []

        # Build AND + OR queries, both quoted via the safe_fts_term cleaner
        and_query = " AND ".join(terms)
        or_query = " OR ".join(terms)
        procedural = cls._looks_procedural(query)
        boost = cls.DOCS_BOOST_PROCEDURAL if procedural else cls.DOCS_BOOST_DEFAULT
        # Pull a generous candidate pool so the per-archive cap doesn't
        # leave us short on the final top_k.
        candidate_pool = max(top_k * 4, 24)
        seen_ids: set[int] = set()
        merged: list[tuple] = []

        # ── 0. Bullseye pass: archives whose NAME matches a query term ──
        # (e.g. "python" → devdocs_en_python). Those articles are usually
        # exactly what the user wants even if they don't repeat the language
        # name. We strip terms already covered by the archive name from the
        # body FTS query so we look for the real concept (define, function)
        # within the right archive.
        bullseye_archives, name_terms = cls._archives_matching_terms(db, terms)
        if bullseye_archives:
            other_terms = [t for t in terms if t not in name_terms]
            if other_terms:
                # AND of remaining terms — restricted to bullseye archives
                sub_query = " AND ".join(other_terms) if len(other_terms) > 1 else other_terms[0]
            else:
                # Whole query consisted of archive-name terms — OR-fallback
                sub_query = " OR ".join(terms)
            try:
                bullseye_rows = cls._run_fts(
                    db, sub_query, candidate_pool, archive_ids=list(bullseye_archives),
                )
                for row in bullseye_rows:
                    if row[0] not in seen_ids:
                        merged.append(row)
                        seen_ids.add(row[0])
            except Exception as exc:
                logger.warning("RAG bullseye query failed (%s) — skipping.", exc)

        # ── 1. AND first across all archives ─────────────────────────
        try:
            and_rows = cls._run_fts(db, and_query, candidate_pool)
            for row in and_rows:
                if row[0] not in seen_ids:
                    merged.append(row)
                    seen_ids.add(row[0])
        except Exception as exc:  # FTS5 parse / bad term — fall through
            logger.warning("RAG AND query failed (%s) — falling back to OR.", exc)

        # ── 2. Augment with OR if still thin ─────────────────────────
        if len(merged) < max(top_k // 2, 3):
            try:
                or_rows = cls._run_fts(db, or_query, candidate_pool)
                for row in or_rows:
                    if row[0] not in seen_ids:
                        merged.append(row)
                        seen_ids.add(row[0])
            except Exception as exc:
                logger.warning("RAG OR query failed: %s", exc)

        # ── 3. Apply boosts (bullseye > docs > none > Q&A) ───────────
        # BM25 scores are negative; lower (more negative) = better. We
        # boost docs (multiply by > 1, more negative) and penalize Q&A
        # (multiply by < 1, less negative). Bullseye gets both a big
        # multiplier AND a fixed bonus so a short-summary docs page wins
        # over a Q&A page whose title happens to contain all keywords.
        qa_penalty = cls.QA_PENALTY_PROCEDURAL if procedural else cls.QA_PENALTY_DEFAULT
        scored = []
        for row in merged:
            arc_id = row[1]
            arc_name = row[6] or ""
            rank = float(row[7])
            if arc_id in bullseye_archives:
                adj = rank * cls.ARCHIVE_NAME_BOOST + cls.ARCHIVE_NAME_BONUS
            elif cls._is_docs_archive(arc_name):
                adj = rank * boost
            elif cls._is_qa_archive(arc_name):
                adj = rank * qa_penalty
            else:
                adj = rank
            scored.append((adj, row))
        scored.sort(key=lambda x: x[0])

        # ── 4. Per-archive diversity cap ─────────────────────────────
        per_arc_count: dict[str, int] = {}
        final: list[RagSource] = []
        n = 0
        for adj, row in scored:
            archive_id = row[1]
            if per_arc_count.get(archive_id, 0) >= cls.MAX_PER_ARCHIVE:
                continue
            per_arc_count[archive_id] = per_arc_count.get(archive_id, 0) + 1
            n += 1
            final.append(RagSource(
                n=n,
                article_id=row[0],
                archive_id=archive_id,
                title=row[2],
                path=row[3],
                summary=row[4] or "",
                archive_title=row[5],
                archive_name=row[6] or "",
                score=adj,
            ))
            if n >= top_k:
                break

        logger.debug(
            "RAG retrieve: q=%r terms=%s procedural=%s -> %d sources",
            query, terms, procedural, len(final),
        )
        return final

    @staticmethod
    def _round_to_sentence(text_in: str, max_len: int = 280) -> str:
        """Truncate text to <= max_len chars, rounding back to a sentence
        boundary (.!?). Falls back to last space, finally a hard cut."""
        if len(text_in) <= max_len:
            return text_in.rstrip()
        cut = text_in[:max_len]
        for end in (".", "!", "?"):
            idx = cut.rfind(end)
            if idx >= max_len - 80:
                return cut[: idx + 1].rstrip()
        sp = cut.rfind(" ")
        return (cut[:sp] if sp > 0 else cut).rstrip() + "…"

    @staticmethod
    def assess_overlap(query: str, sources: List[RagSource]) -> int:
        """Count how many sources mention at least one query keyword in
        their summary. Used to decide whether to hint to the model that
        the sources are loose."""
        kws = [k.lower() for k in RagService.extract_keywords(query)]
        if not kws:
            return len(sources)
        hits = 0
        for s in sources:
            text_l = (s.title + " " + s.summary).lower()
            if any(k in text_l for k in kws):
                hits += 1
        return hits

    # Per-message cap when stitching prior turns into the prompt.  Keeps the
    # whole context window under control — Gemma 3 1B has n_ctx=2048 and we
    # also need room for sources (~350) + instructions (~150) + answer (~256).
    HISTORY_MSG_CAP = 600
    MAX_HISTORY_TURNS = 8  # 4 user + 4 assistant typically

    @classmethod
    def build_prompt(
        cls,
        question: str,
        sources: List[RagSource],
        history: Optional[List[dict]] = None,
    ) -> str:
        """
        Compose a multi-turn Gemma 3 chat prompt.

        Includes up to MAX_HISTORY_TURNS prior messages (each capped at
        HISTORY_MSG_CAP chars) so the model has working context, followed by
        the system instructions, sources, and the new question.
        """
        if not sources:
            sources_block = "(no sources found in the indexed archives)"
            sources_are_loose = True
        else:
            lines = []
            for s in sources:
                snippet = cls._round_to_sentence(s.summary, 280)
                lines.append(f"[{s.n}] {s.title} — {snippet}")
            sources_block = "\n".join(lines)
            # "Loose" = fewer than 2 sources clearly overlap with the query
            sources_are_loose = cls.assess_overlap(question, sources) < 2

        base_instructions = (
            "You are a helpful research assistant. Prefer the SOURCES below for any factual claims, "
            "and cite them with the matching number in square brackets, e.g. [1] or [2].\n"
            "If the user refers to earlier turns in this conversation, use that context too.\n"
            "\n"
            "Format your answer with proper Markdown:\n"
            "- Open with a one-sentence summary on its own line.\n"
            "- Then provide details as short paragraphs separated by BLANK LINES.\n"
            "- Use **bold** for key terms and concepts.\n"
            "- Use bullet points (lines starting with `- `) for lists of 2+ items.\n"
            "- Use `inline code` for code/identifiers and ```language fenced blocks for multi-line code.\n"
            "- Use ### Subheading lines if the answer needs sections.\n"
            "\n"
            "Keep the whole answer focused — typically 3-8 sentences plus any bullet list.\n"
        )
        if sources_are_loose:
            # Don't dead-end the user when retrieval is weak. Let the model
            # fall back to general knowledge, but require it to flag that part.
            tail = (
                "If a SOURCE clearly answers the question, cite it. If the sources are only "
                "loosely related, give a brief answer from general knowledge AND begin that "
                "part with the prefix \"From general knowledge:\" so the user knows it isn't cited."
            )
        else:
            tail = (
                "Use ONLY information present in the SOURCES. If they don't contain the answer, "
                'reply exactly: "I could not find this in the indexed archives." Never invent facts.'
            )
        instructions = base_instructions + tail

        # ── Multi-turn history block ──────────────────────────────────
        parts: list[str] = []
        if history:
            # Trim citation chips out of prior assistant turns to save tokens —
            # numbers no longer map to the current source list.
            cite_re = re.compile(r"\s*\[\d+\]")
            recent = history[-cls.MAX_HISTORY_TURNS:]
            for turn in recent:
                role = turn.get("role")
                content = (turn.get("content") or "").strip()
                if not content or role not in ("user", "assistant"):
                    continue
                if role == "assistant":
                    content = cite_re.sub("", content)
                content = content[: cls.HISTORY_MSG_CAP]
                tag = "user" if role == "user" else "model"
                parts.append(f"<start_of_turn>{tag}\n{content}<end_of_turn>")

        # ── Final user turn with instructions + sources + new question ─
        parts.append(
            "<start_of_turn>user\n"
            f"{instructions}\n\n"
            f"SOURCES:\n{sources_block}\n\n"
            f"QUESTION: {question}<end_of_turn>"
        )
        parts.append("<start_of_turn>model\n")
        return "\n".join(parts)
