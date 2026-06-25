import re
import json
import config
from document_identity import metadata_allows_user
from utils import clear_directory_contents
from pathlib import Path
from typing import List, Dict

class ParentStoreManager:
    __store_path: Path

    def __init__(self, store_path=config.PARENT_STORE_PATH):
        self.__store_path = Path(store_path) 
        self.__store_path.mkdir(parents=True, exist_ok=True)

    def save(self, parent_id: str, content: str, metadata: Dict) -> None:
        file_path = self._path_for_parent(parent_id, metadata)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps({"page_content": content,"metadata": metadata}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def save_many(self, parents: List) -> None:
        for parent_id, doc in parents:
            self.save(parent_id, doc.page_content, doc.metadata)

    def load(self, parent_id: str) -> Dict:
        file_path = self._find_parent_path(parent_id)
        return json.loads(file_path.read_text(encoding="utf-8"))
    
    def load_content(self, parent_id: str, *, user_id: str | None = None) -> Dict:
        data = self.load(parent_id)
        if not metadata_allows_user(data.get("metadata"), user_id):
            raise PermissionError(f"Parent chunk is not accessible for user_id={user_id}")
        return {
                "content": data["page_content"],
                "parent_id": parent_id,
                "metadata": data["metadata"]
            }

    @staticmethod
    def _get_sort_key(id_str):
        match = re.search(r'_parent_(\d+)$', id_str)
        return int(match.group(1)) if match else 0

    def load_content_many(self, parent_ids: List[str], *, user_id: str | None = None) -> List[Dict]:
        unique_ids = set(parent_ids)
        return [
            self.load_content(pid, user_id=user_id)
            for pid in sorted(unique_ids, key=self._get_sort_key)
        ]
    
    def clear_store(self) -> None:
        self.__store_path.mkdir(parents=True, exist_ok=True)
        clear_directory_contents(self.__store_path)

    def delete_by_document(self, *, document_id: str, user_id: str | None = None) -> int:
        deleted = 0
        for file_path in self.__store_path.rglob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            metadata = data.get("metadata") or {}
            if str(metadata.get("document_id") or "") != str(document_id):
                continue
            if user_id is not None and str(metadata.get("user_id") or "") != str(user_id):
                continue

            file_path.unlink()
            deleted += 1

        self._remove_empty_dirs()
        return deleted

    def clear_by_user(self, user_id: str) -> int:
        deleted = 0
        for file_path in self.__store_path.rglob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            metadata = data.get("metadata") or {}
            if str(metadata.get("user_id") or "") != str(user_id):
                continue
            if str(metadata.get("visibility") or "").lower() != "private":
                continue

            file_path.unlink()
            deleted += 1

        self._remove_empty_dirs()
        return deleted

    def _path_for_parent(self, parent_id: str, metadata: Dict | None = None) -> Path:
        metadata = metadata or {}
        visibility = str(metadata.get("visibility") or "").lower()
        user_id = str(metadata.get("user_id") or "").strip()
        document_id = str(metadata.get("document_id") or "").strip()

        if visibility == "private" and user_id and document_id:
            return self.__store_path / "private" / user_id / f"{parent_id}.json"
        if visibility == "public" and document_id:
            return self.__store_path / "public" / f"{parent_id}.json"
        return self.__store_path / f"{parent_id}.json"

    def _find_parent_path(self, parent_id: str) -> Path:
        filename = parent_id if parent_id.lower().endswith(".json") else f"{parent_id}.json"
        direct_path = self.__store_path / filename
        if direct_path.exists():
            return direct_path

        matches = list(self.__store_path.rglob(filename))
        if matches:
            return matches[0]

        return direct_path

    def _remove_empty_dirs(self) -> None:
        for child in sorted(self.__store_path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass
