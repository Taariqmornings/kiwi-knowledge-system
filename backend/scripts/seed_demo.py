"""
seed_demo.py — Populate the Kiwi database with sample articles for demo purposes.

Run this script INSTEAD of indexing real ZIM files when you want to try the
search, browsing, and RAG chat features immediately without downloading large
ZIM archives.

Usage (from the repo root):
    # Windows
    python backend/scripts/seed_demo.py

    # macOS / Linux
    python3 backend/scripts/seed_demo.py

What it creates:
  - 1 virtual "Demo Archive" entry  (no actual .zim file needed)
  - 30 sample articles covering science, technology, history, and more
  - Full FTS5 search index over all sample content

After running, start the backend normally and you can immediately:
  - Search for terms like "photosynthesis", "python", "gravity", "evolution"
  - Browse categories
  - Open articles in the reader (they render as simple HTML pages)
"""

from __future__ import annotations

import sys
import os

# Make sure we can import the app regardless of the working directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core.database import engine, Base
from app.database_models import Archive, Article
from sqlalchemy.orm import Session
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Sample articles
# Each entry: (title, path, keywords, summary, mimetype)
# ---------------------------------------------------------------------------
DEMO_ARTICLES: list[tuple[str, str, str, str, str]] = [
    # Science
    (
        "Photosynthesis",
        "A/Photosynthesis.html",
        "photosynthesis | chlorophyll | light energy | glucose | plants | biology",
        "Photosynthesis is the process used by plants, algae, and certain bacteria "
        "to convert light energy, usually from the sun, into chemical energy stored "
        "in glucose. The overall reaction converts carbon dioxide and water into "
        "glucose and oxygen using light energy captured by chlorophyll.",
        "text/html",
    ),
    (
        "Gravity",
        "A/Gravity.html",
        "gravity | Newton | Einstein | general relativity | mass | force",
        "Gravity is a fundamental force of nature that attracts objects with mass "
        "toward each other. Isaac Newton first described it mathematically, and "
        "Albert Einstein later explained it as the curvature of spacetime in his "
        "General Theory of Relativity.",
        "text/html",
    ),
    (
        "DNA and Genetics",
        "A/DNA.html",
        "DNA | genetics | chromosomes | genes | heredity | double helix | Watson | Crick",
        "Deoxyribonucleic acid (DNA) is the molecule that carries the genetic "
        "instructions for the development, functioning, and reproduction of all "
        "known living organisms. It consists of two strands forming a double helix, "
        "discovered by James Watson and Francis Crick in 1953.",
        "text/html",
    ),
    (
        "Evolution by Natural Selection",
        "A/Evolution.html",
        "evolution | Darwin | natural selection | species | adaptation | survival",
        "Evolution by natural selection, proposed by Charles Darwin in 1859, "
        "explains how populations of organisms change over generations through "
        "the differential survival and reproduction of individuals with heritable "
        "traits better suited to their environment.",
        "text/html",
    ),
    (
        "Quantum Mechanics",
        "A/Quantum_Mechanics.html",
        "quantum | wave function | uncertainty | Heisenberg | Schrödinger | photon | electron",
        "Quantum mechanics is a fundamental theory in physics describing nature at "
        "the smallest scales of energy levels of atoms and subatomic particles. It "
        "introduces concepts such as wave-particle duality, the uncertainty principle, "
        "and quantised energy levels.",
        "text/html",
    ),
    (
        "The Water Cycle",
        "A/Water_Cycle.html",
        "water cycle | evaporation | precipitation | condensation | hydrology | rain",
        "The water cycle, also known as the hydrological cycle, describes the "
        "continuous movement of water on, above, and below Earth's surface through "
        "processes including evaporation, condensation, precipitation, and runoff.",
        "text/html",
    ),
    # Technology & Computing
    (
        "Python Programming Language",
        "A/Python_Programming_Language.html",
        "Python | programming | Guido van Rossum | interpreter | scripting | syntax",
        "Python is a high-level, general-purpose programming language known for its "
        "clear syntax and readability. Created by Guido van Rossum and first released "
        "in 1991, it supports multiple programming paradigms including procedural, "
        "object-oriented, and functional programming.",
        "text/html",
    ),
    (
        "Machine Learning",
        "A/Machine_Learning.html",
        "machine learning | AI | neural network | training data | algorithm | model",
        "Machine learning is a branch of artificial intelligence that enables systems "
        "to learn and improve from experience without being explicitly programmed. "
        "It focuses on building systems that can access data and use it to learn for "
        "themselves.",
        "text/html",
    ),
    (
        "The Internet",
        "A/The_Internet.html",
        "internet | TCP/IP | ARPANET | HTTP | web | network | protocol",
        "The Internet is a global system of interconnected computer networks that "
        "use the Internet protocol suite (TCP/IP) to communicate between networks "
        "and devices. It grew from ARPANET, a US Department of Defense research "
        "project in the late 1960s.",
        "text/html",
    ),
    (
        "Linux Operating System",
        "A/Linux.html",
        "Linux | kernel | Linus Torvalds | open source | Unix | operating system",
        "Linux is a family of open-source Unix-like operating systems based on the "
        "Linux kernel, first released by Linus Torvalds in 1991. Distributed under "
        "the GNU General Public License, it is one of the most prominent examples "
        "of free and open-source software.",
        "text/html",
    ),
    (
        "Cryptography",
        "A/Cryptography.html",
        "cryptography | encryption | RSA | AES | public key | cipher | security",
        "Cryptography is the practice of securing communications and information "
        "through the use of codes, ciphers, and mathematical algorithms. Modern "
        "cryptography underpins internet security through protocols like TLS and "
        "algorithms such as RSA and AES.",
        "text/html",
    ),
    (
        "Databases and SQL",
        "A/Databases_SQL.html",
        "database | SQL | relational | PostgreSQL | MySQL | SQLite | query | table",
        "A database is an organised collection of structured information or data. "
        "Relational databases store data in tables with rows and columns, accessed "
        "via Structured Query Language (SQL). Popular systems include PostgreSQL, "
        "MySQL, and SQLite.",
        "text/html",
    ),
    # Mathematics
    (
        "The Pythagorean Theorem",
        "A/Pythagorean_Theorem.html",
        "Pythagorean theorem | geometry | right angle | hypotenuse | mathematics | proof",
        "The Pythagorean theorem states that in a right-angled triangle, the square "
        "of the length of the hypotenuse equals the sum of the squares of the other "
        "two sides. Written as a² + b² = c², it is one of the most fundamental "
        "results in Euclidean geometry.",
        "text/html",
    ),
    (
        "Calculus",
        "A/Calculus.html",
        "calculus | derivative | integral | Newton | Leibniz | limits | differentiation",
        "Calculus is a branch of mathematics that deals with rates of change "
        "(differential calculus) and accumulation of quantities (integral calculus). "
        "Developed independently by Isaac Newton and Gottfried Wilhelm Leibniz in "
        "the 17th century, it is foundational to science and engineering.",
        "text/html",
    ),
    (
        "Prime Numbers",
        "A/Prime_Numbers.html",
        "prime numbers | mathematics | Sieve of Eratosthenes | number theory | infinity",
        "A prime number is a natural number greater than 1 that has no positive "
        "divisors other than 1 and itself. The first few primes are 2, 3, 5, 7, 11. "
        "Euclid proved there are infinitely many primes around 300 BCE.",
        "text/html",
    ),
    # History
    (
        "The French Revolution",
        "A/French_Revolution.html",
        "French Revolution | 1789 | Bastille | Napoleon | liberty | equality | France",
        "The French Revolution was a period of radical political and societal change "
        "in France from 1789 to 1799. It overthrew the monarchy, established a "
        "republic, culminated in Napoleon's rise to power, and had a lasting impact "
        "on world history with its ideals of liberty, equality, and fraternity.",
        "text/html",
    ),
    (
        "World War II",
        "A/World_War_II.html",
        "World War II | 1939 | 1945 | Hitler | Allied | Axis | Holocaust | D-Day",
        "World War II was a global conflict that lasted from 1939 to 1945, involving "
        "most of the world's nations forming two opposing alliances: the Allies and "
        "the Axis. It was the most destructive conflict in human history, resulting "
        "in 70–85 million fatalities.",
        "text/html",
    ),
    (
        "The Industrial Revolution",
        "A/Industrial_Revolution.html",
        "Industrial Revolution | steam engine | factory | Britain | 18th century | manufacturing",
        "The Industrial Revolution was the transition to new manufacturing processes "
        "in Great Britain from about 1760 to 1840. It included the shift from hand "
        "production to machine-based methods, steam power, and the rise of the "
        "factory system.",
        "text/html",
    ),
    (
        "Ancient Rome",
        "A/Ancient_Rome.html",
        "Rome | Roman Empire | Julius Caesar | republic | senate | Latin | gladiators",
        "Ancient Rome was a civilisation that grew from the Italian peninsula beginning "
        "in the 8th century BC. From a small city-state it expanded to dominate "
        "Western Europe, North Africa, and the Middle East at its height, leaving "
        "an enduring legacy in law, language, and governance.",
        "text/html",
    ),
    # Geography & Nature
    (
        "The Amazon Rainforest",
        "A/Amazon_Rainforest.html",
        "Amazon | rainforest | biodiversity | deforestation | Brazil | ecosystem | jungle",
        "The Amazon rainforest is a vast tropical rainforest occupying the Amazon "
        "basin in South America. Covering over 5.5 million km², it is the world's "
        "largest tropical rainforest and contains an enormous diversity of plant "
        "and animal species.",
        "text/html",
    ),
    (
        "Mount Everest",
        "A/Mount_Everest.html",
        "Everest | Himalayas | altitude | mountaineering | Nepal | Tibet | summit",
        "Mount Everest is Earth's highest mountain above sea level, located in the "
        "Himalayas on the border between Nepal and Tibet. Its peak is 8,848.86 metres "
        "above sea level. Edmund Hillary and Tenzing Norgay first reached the summit "
        "on 29 May 1953.",
        "text/html",
    ),
    (
        "Climate Change",
        "A/Climate_Change.html",
        "climate change | global warming | greenhouse gas | CO2 | IPCC | emissions | temperature",
        "Climate change refers to long-term shifts in global temperatures and weather "
        "patterns. While some changes are natural, since the mid-20th century human "
        "activities, primarily burning fossil fuels, have been the dominant driver "
        "of observed climate change.",
        "text/html",
    ),
    # Medicine & Health
    (
        "The Human Immune System",
        "A/Immune_System.html",
        "immune system | antibodies | white blood cells | vaccination | infection | T cells",
        "The immune system is a complex network of cells, proteins, tissues, and "
        "organs that defends the body against pathogens and disease. It distinguishes "
        "the body's own cells from foreign cells and neutralises threats through "
        "innate and adaptive responses.",
        "text/html",
    ),
    (
        "Vaccines and Immunisation",
        "A/Vaccines.html",
        "vaccines | immunisation | Jenner | smallpox | COVID-19 | herd immunity | mRNA",
        "A vaccine is a biological preparation that provides active acquired immunity "
        "to a particular infectious disease. Vaccines stimulate the immune system to "
        "recognise and fight specific pathogens without causing the disease itself.",
        "text/html",
    ),
    (
        "Nutrition and the Human Body",
        "A/Nutrition.html",
        "nutrition | vitamins | protein | carbohydrates | fat | metabolism | diet",
        "Nutrition is the science of how the body obtains and uses nutrients from "
        "food. Essential nutrients include macronutrients (carbohydrates, proteins, "
        "fats) and micronutrients (vitamins and minerals), each playing critical "
        "roles in body function and health.",
        "text/html",
    ),
    # Philosophy & Literature
    (
        "Stoicism",
        "A/Stoicism.html",
        "Stoicism | Marcus Aurelius | Epictetus | Seneca | philosophy | virtue | logic",
        "Stoicism is an ancient Greek and Roman philosophy founded in Athens by Zeno "
        "of Citium in the 3rd century BC. It teaches that virtue is the highest good "
        "and that humans should accept events calmly, develop self-control, and "
        "focus only on what is within their control.",
        "text/html",
    ),
    (
        "William Shakespeare",
        "A/William_Shakespeare.html",
        "Shakespeare | Hamlet | Macbeth | sonnets | Elizabethan | theatre | poetry",
        "William Shakespeare (1564–1616) was an English playwright, poet, and actor "
        "widely regarded as the greatest writer in the English language. His works "
        "include 39 plays, 154 sonnets, and several long poems that continue to be "
        "performed and studied worldwide.",
        "text/html",
    ),
    # Economics
    (
        "Supply and Demand",
        "A/Supply_and_Demand.html",
        "economics | supply | demand | price | market | equilibrium | Adam Smith",
        "Supply and demand is a fundamental economic model that describes price "
        "determination in a market. When supply exceeds demand, prices fall; when "
        "demand exceeds supply, prices rise. The market clearing price is reached "
        "at equilibrium.",
        "text/html",
    ),
    (
        "The Stock Market",
        "A/Stock_Market.html",
        "stock market | shares | NYSE | investment | equities | dividends | bull bear",
        "A stock market is a public market where company shares are issued and traded "
        "through exchanges or over-the-counter. The stock market allows companies to "
        "raise capital and gives investors the opportunity to share in the financial "
        "achievements of publicly listed companies.",
        "text/html",
    ),
    # Space
    (
        "The Solar System",
        "A/Solar_System.html",
        "solar system | planets | Sun | Mercury | Venus | Earth | Mars | Jupiter | Saturn",
        "The Solar System consists of the Sun and all the celestial objects bound "
        "to it by gravity, including eight planets, their moons, dwarf planets, "
        "asteroids, comets, and interplanetary dust. It formed approximately "
        "4.6 billion years ago.",
        "text/html",
    ),
]


def seed(verbose: bool = True) -> None:
    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        # ------------------------------------------------------------------
        # Create (or reuse) the demo archive record
        # ------------------------------------------------------------------
        DEMO_ARCHIVE_ID = "demo-archive-kiwi-seed-v1"
        archive = db.get(Archive, DEMO_ARCHIVE_ID)

        if archive is None:
            archive = Archive(
                id=DEMO_ARCHIVE_ID,
                name="kiwi-demo.zim",
                title="Kiwi Demo Archive",
                description="Sample articles seeded for demonstration. Not a real ZIM file.",
                path="/demo/kiwi-demo.zim",  # non-existent; reader will show error
                language="eng",
                creator="Kiwi Project",
                date="2026-06-25",
                size_bytes=0,
                article_count=len(DEMO_ARTICLES),
                indexed_count=len(DEMO_ARTICLES),
                status="indexed",
            )
            db.add(archive)
            db.flush()
            if verbose:
                print(f"  Created demo archive  -> id: {DEMO_ARCHIVE_ID}")
        else:
            if verbose:
                print(f"  Demo archive already exists (id: {DEMO_ARCHIVE_ID}) — updating articles.")
            # Remove old demo articles so we can re-insert cleanly
            db.query(Article).filter(Article.archive_id == DEMO_ARCHIVE_ID).delete()

        # ------------------------------------------------------------------
        # Insert articles
        # ------------------------------------------------------------------
        inserted = 0
        for title, path, keywords, summary, mimetype in DEMO_ARTICLES:
            article = Article(
                archive_id=DEMO_ARCHIVE_ID,
                title=title,
                path=path,
                keywords=keywords,
                summary=summary,
                mimetype=mimetype,
            )
            db.add(article)
            inserted += 1

        db.commit()
        if verbose:
            print(f"  Inserted {inserted} demo articles.")

        # ------------------------------------------------------------------
        # Populate the FTS5 index
        # ------------------------------------------------------------------
        # articles_fts is an external-content FTS5 table (content='articles')
        # with columns: title, summary, keywords. We insert ONLY the demo rows
        # by rowid rather than running a full 'rebuild' — a rebuild would
        # reprocess every article in the database, which is extremely slow if
        # you already have real ZIM archives indexed (potentially millions of
        # rows).
        fts_exists = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='articles_fts'")
        ).fetchone()

        if fts_exists:
            rows = db.execute(
                text(
                    "SELECT id, title, summary, keywords "
                    "FROM articles WHERE archive_id = :aid"
                ),
                {"aid": DEMO_ARCHIVE_ID},
            ).fetchall()
            for row in rows:
                db.execute(
                    text("INSERT INTO articles_fts(rowid, title, summary, keywords) "
                         "VALUES (:rowid, :title, :summary, :keywords)"),
                    {"rowid": row.id, "title": row.title,
                     "summary": row.summary or "", "keywords": row.keywords or ""},
                )
            db.commit()
            if verbose:
                print(f"  FTS5 index updated ({len(rows)} demo entries).")
        else:
            if verbose:
                print(
                    "  FTS5 table not found - start the backend once first so migrations run, "
                    "then re-run this script."
                )

    if verbose:
        print()
        print("  Demo data seeded successfully.")
        print("  Start the backend and open http://localhost:5173 to explore Kiwi.")


if __name__ == "__main__":
    print()
    print("  Kiwi - Demo Data Seeder")
    print("  " + "-" * 40)
    seed(verbose=True)
