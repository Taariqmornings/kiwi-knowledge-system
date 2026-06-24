import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from libzim.reader import Archive as ZimArchive

from app.database_models import Archive, Category, archive_categories
from app.core.config import ZIM_DIR

# Keyword lists used to auto-assign categories when a ZIM file is registered.
# Matching is case-insensitive against title + description + filename + filename stem (underscore-split).
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Medicine":          ["medicine", "medical", "health", "anatomy", "drug", "pharmacy",
                          "clinical", "disease", "symptom", "medline", "physiology",
                          "nursing", "dentist", "psych", "mental", "pathology",
                          "msd", "mdmanual", "medicinenet", "webmd", "mayoclinic",
                          "nhs", "who", "anat", "physio", "cardio", "neuro",
                          "oncology", "pediatric", "surgery", "pharma", "biomed"],
    "Science":           ["science", "physics", "chemistry", "ecology",
                          "astronomy", "geology", "botany", "zoology", "natural",
                          "biology", "microbio", "genetics", "climate", "nasa",
                          "solar", "planet", "element", "molecule", "lab", "experiment",
                          "scientific", "chem", "physic"],
    "Engineering":       ["engineering", "mechanical", "electrical", "electronics",
                          "civil", "aerospace", "robotics", "manufacturing",
                          "circuit", "arduino", "raspberry", "automotive",
                          "structural", "thermo", "fluid", "control"],
    "History":           ["history", "historical", "heritage", "ancient", "civilization",
                          "war", "empire", "archaeology", "medieval", "renaissance",
                          "revolution", "century", "biography", "timeline",
                          "wwi", "wwii", "coldwar", "colonial", "dynasty"],
    "Geography":         ["geography", "world", "country", "countries", "atlas",
                          "maps", "nation", "climate", "region", "continent",
                          "capital", "population", "topography", "geospatial",
                          "gis", "latitude", "longitude"],
    "Coding":            ["coding", "programming", "developer", "devdocs",
                          "software", "javascript", "python", "linux", "ubuntu",
                          "stackexchange", "stackoverflow", "computer", "algorithm",
                          "database", "html", "css", "typescript", "rust", "java",
                          "cpp", "react", "angular", "vue", "node", "docker",
                          "kubernetes", "git", "api", "sql", "nosql", "mongodb",
                          "postgres", "swift", "kotlin", "go lang", "ruby", "php",
                          "bash", "shell", "unix", "devops", "frontend", "backend",
                          "webdev", "app dev"],
    "Mathematics":       ["math", "mathematics", "calculus", "statistics",
                          "algebra", "geometry", "probability", "trigonometry",
                          "arithmetic", "equation", "function", "graph",
                          "matrix", "vector", "derivative", "integral",
                          "number theory", "discrete", "logic"],
    "Survival":          ["survival", "wilderness", "first aid", "emergency",
                          "preparedness", "disaster", "bushcraft", "off grid",
                          "camping", "hiking", "navigation", "foraging",
                          "selfsufficient", "prepper", "shtf", "outdoor"],
    "Education":         ["education", "school", "learning", "university",
                          "tutorial", "textbook", "wikibooks", "wikiversity",
                          "course", "lesson", "study", "curriculum", "lecture",
                          "classroom", "academic", "pedagogy", "khanacademy",
                          "ted", "coursera", "edx"],
    "General Knowledge": ["wikipedia", "encyclopedia", "wiktionary", "general",
                          "culture", "society", "arts", "literature", "reference",
                          "almanac", "factbook", "knowledge", "wiki", "library",
                          "britannica", "citizendium"],
}


class ArchiveService:
    @staticmethod
    def _is_safe_path(target: str, allow_list: Optional[List[str]] = None) -> bool:
        """Validate that a path doesn't contain path traversal attempts."""
        # Check for null bytes
        if "\0" in target:
            return False
        # Reject relative paths
        if not os.path.isabs(target):
            return False
        # Block path traversal components
        normalized = target.replace("\\", "/")
        parts = normalized.split("/")
        if ".." in parts:
            return False
        return True

    @staticmethod
    def _validate_entry_path(entry_path: str) -> str:
        """Sanitize and validate a ZIM entry path."""
        if not entry_path or "\0" in entry_path:
            raise ValueError("Invalid entry path: null bytes detected")
        # Normalize path separators
        cleaned = entry_path.replace("\\", "/")
        # Decode URL-encoded sequences that could mask traversal
        cleaned = cleaned.replace("%2e", ".").replace("%2E", ".")
        # Block path traversal in entry paths
        if ".." in cleaned.split("/"):
            raise ValueError("Path traversal detected in entry path")
        # Block absolute paths
        if cleaned.startswith("/"):
            raise ValueError("Absolute entry path not allowed")
        return cleaned

    @staticmethod
    def get_archive_id(filepath: str) -> str:
        """Generate a deterministic unique ID based on the file path."""
        return hashlib.md5(str(filepath).encode('utf-8')).hexdigest()

    @staticmethod
    def read_zim_metadata(filepath: str) -> Dict:
        """Open a ZIM archive and read its metadata and dimensions."""
        if not ArchiveService._is_safe_path(filepath):
            raise ValueError(f"Invalid file path: {filepath}")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"ZIM file not found: {filepath}")

        zim = ZimArchive(filepath)
        metadata = {
            "title": "",
            "description": "",
            "creator": "",
            "date": "",
            "language": "",
            "article_count": zim.article_count,
            "all_entry_count": zim.all_entry_count,
            "has_main_entry": zim.has_main_entry,
            "main_entry_path": ""
        }

        for key in ["Title", "Description", "Creator", "Date", "Language"]:
            try:
                val = zim.get_metadata(key)
                if isinstance(val, bytes):
                    val = val.decode('utf-8', errors='ignore')
                metadata[key.lower()] = val
            except Exception:
                pass

        if not metadata["title"]:
            metadata["title"] = os.path.basename(filepath)

        if zim.has_main_entry:
            try:
                metadata["main_entry_path"] = zim.main_entry.path
            except Exception:
                pass

        return metadata

    @classmethod
    def _auto_categorize(cls, db: Session, archive: Archive, title: str, description: str, filename: str) -> None:
        """Assign categories to an archive by keyword-matching its metadata."""
        haystack = " ".join([title or "", description or "", filename or ""]).lower()
        categories = db.query(Category).all()
        cat_map = {c.name: c for c in categories}
        matched = [
            cat_map[name]
            for name, keywords in _CATEGORY_KEYWORDS.items()
            if name in cat_map and any(kw in haystack for kw in keywords)
        ]
        if not matched and "General Knowledge" in cat_map:
            matched = [cat_map["General Knowledge"]]
        for cat in matched:
            db.execute(
                archive_categories.insert().prefix_with("OR IGNORE").values(
                    archive_id=archive.id, category_id=cat.id
                )
            )
        db.commit()

    @classmethod
    def add_files(cls, db: Session, file_paths: List[str]) -> List[Archive]:
        """Register individual ZIM files and auto-categorize them."""
        results = []
        for fp in file_paths:
            abs_path = str(Path(fp).resolve())
            if not cls._is_safe_path(abs_path):
                continue
            if not abs_path.lower().endswith(".zim") or not os.path.isfile(abs_path):
                continue
            archive_id = cls.get_archive_id(abs_path)
            existing = db.query(Archive).filter(Archive.id == archive_id).first()
            if existing:
                results.append(existing)
                continue
            try:
                meta = cls.read_zim_metadata(abs_path)
                new_archive = Archive(
                    id=archive_id,
                    name=Path(abs_path).name,
                    path=abs_path,
                    title=meta["title"],
                    description=meta["description"],
                    creator=meta["creator"],
                    date=meta["date"],
                    language=meta["language"],
                    size_bytes=os.path.getsize(abs_path),
                    article_count=meta["article_count"],
                    status="idle",
                    indexed_count=0,
                )
                db.add(new_archive)
                db.commit()
                db.refresh(new_archive)
                cls._auto_categorize(db, new_archive, meta["title"], meta["description"], Path(abs_path).name)
                results.append(new_archive)
            except Exception as e:
                print(f"[ArchiveService] Failed to add {abs_path}: {e}")
                db.rollback()
        return results

    @classmethod
    def scan_directory(cls, db: Session, directory_path: str) -> List[Archive]:
        """Scan a directory for ZIM files and add new ones to the DB in 'idle' state."""
        if not cls._is_safe_path(directory_path):
            return []

        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            return []

        imported_archives = []
        zim_files = list(path.glob("**/*.zim")) + list(path.glob("**/*.ZIM"))
        zim_files = list(set(zim_files))

        for file_path in zim_files:
            abs_path = str(file_path.resolve())
            archive_id = cls.get_archive_id(abs_path)

            db_archive = db.query(Archive).filter(Archive.id == archive_id).first()
            if db_archive:
                imported_archives.append(db_archive)
                continue

            try:
                meta = cls.read_zim_metadata(abs_path)
                file_size = os.path.getsize(abs_path)

                new_archive = Archive(
                    id=archive_id,
                    name=file_path.name,
                    path=abs_path,
                    title=meta["title"],
                    description=meta["description"],
                    creator=meta["creator"],
                    date=meta["date"],
                    language=meta["language"],
                    size_bytes=file_size,
                    article_count=meta["article_count"],
                    status="idle",
                    indexed_count=0
                )
                db.add(new_archive)
                db.commit()
                db.refresh(new_archive)
                cls._auto_categorize(db, new_archive, meta["title"], meta["description"], file_path.name)
                imported_archives.append(new_archive)
            except Exception as e:
                print(f"[ArchiveService] Failed to scan {abs_path}: {e}")
                db.rollback()

        return imported_archives

    @staticmethod
    def get_entry_data(filepath: str, entry_path: str) -> Tuple[bytes, str, str]:
        """
        Retrieve raw content, mimetype, and title for a specific entry path in a ZIM file.
        Returns: (content_bytes, mimetype_string, title_string)
        """
        if not ArchiveService._is_safe_path(filepath):
            raise ValueError(f"Invalid file path: {filepath}")
        safe_path = ArchiveService._validate_entry_path(entry_path)

        zim = ZimArchive(filepath)
        if not zim.has_entry_by_path(safe_path):
            raise KeyError(f"Entry path '{safe_path}' not found in ZIM archive.")

        entry = zim.get_entry_by_path(safe_path)

        redirect_count = 0
        while entry.is_redirect and redirect_count < 5:   # is_redirect is a property, not a method
            entry = entry.get_redirect_entry()
            redirect_count += 1

        item = entry.get_item()
        content = bytes(item.content)
        mimetype = item.mimetype
        title = entry.title

        return content, mimetype, title
