import config
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from document_identity import build_parent_id, normalize_document_id, normalize_user_id, normalize_visibility

class DocumentChuncker:
    def __init__(self):
        self.__parent_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=config.HEADERS_TO_SPLIT_ON, 
            strip_headers=False
        )
        self.__child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHILD_CHUNK_SIZE, 
            chunk_overlap=config.CHILD_CHUNK_OVERLAP
        )
        self.__min_parent_size = config.MIN_PARENT_SIZE
        self.__max_parent_size = config.MAX_PARENT_SIZE

    def create_chunks_single(
        self,
        md_path,
        *,
        document_id: str | None = None,
        source_name: str | None = None,
        user_id: str | None = None,
        visibility: str | None = None,
        category: str | None = None,
    ):
        doc_path = Path(md_path)
        
        with open(doc_path, "r", encoding="utf-8") as f:
            parent_chunks = self.__parent_splitter.split_text(f.read())
        
        merged_parents = self.__merge_small_parents(parent_chunks)
        split_parents = self.__split_large_parents(merged_parents)
        cleaned_parents = self.__clean_small_chunks(split_parents)
        
        all_parent_chunks, all_child_chunks = [], []
        self.__create_child_chunks(
            all_parent_chunks,
            all_child_chunks,
            cleaned_parents,
            doc_path,
            document_id=document_id,
            source_name=source_name,
            user_id=user_id,
            visibility=visibility,
            category=category,
        )
        return all_parent_chunks, all_child_chunks

    def __merge_small_parents(self, chunks):
        if not chunks:
            return []
        
        merged, current = [], None
        
        for chunk in chunks:
            if current is None:
                current = chunk
            else:
                current.page_content += "\n\n" + chunk.page_content
                for k, v in chunk.metadata.items():
                    if k in current.metadata:
                        current.metadata[k] = f"{current.metadata[k]} -> {v}"
                    else:
                        current.metadata[k] = v

            if len(current.page_content) >= self.__min_parent_size:
                merged.append(current)
                current = None
        
        if current:
            if merged:
                merged[-1].page_content += "\n\n" + current.page_content
                for k, v in current.metadata.items():
                    if k in merged[-1].metadata:
                        merged[-1].metadata[k] = f"{merged[-1].metadata[k]} -> {v}"
                    else:
                        merged[-1].metadata[k] = v
            else:
                merged.append(current)
        
        return merged

    def __split_large_parents(self, chunks):
        split_chunks = []
        
        for chunk in chunks:
            if len(chunk.page_content) <= self.__max_parent_size:
                split_chunks.append(chunk)
            else:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.__max_parent_size,
                    chunk_overlap=config.CHILD_CHUNK_OVERLAP
                )
                sub_chunks = splitter.split_documents([chunk])
                split_chunks.extend(sub_chunks)
        
        return split_chunks

    def __clean_small_chunks(self, chunks):
        cleaned = []
        
        for i, chunk in enumerate(chunks):
            if len(chunk.page_content) < self.__min_parent_size:
                if cleaned:
                    cleaned[-1].page_content += "\n\n" + chunk.page_content
                    for k, v in chunk.metadata.items():
                        if k in cleaned[-1].metadata:
                            cleaned[-1].metadata[k] = f"{cleaned[-1].metadata[k]} -> {v}"
                        else:
                            cleaned[-1].metadata[k] = v
                elif i < len(chunks) - 1:
                    chunks[i + 1].page_content = chunk.page_content + "\n\n" + chunks[i + 1].page_content
                    for k, v in chunk.metadata.items():
                        if k in chunks[i + 1].metadata:
                            chunks[i + 1].metadata[k] = f"{v} -> {chunks[i + 1].metadata[k]}"
                        else:
                            chunks[i + 1].metadata[k] = v
                else:
                    cleaned.append(chunk)
            else:
                cleaned.append(chunk)
        
        return cleaned

    def __create_child_chunks(
        self,
        all_parent_pairs,
        all_child_chunks,
        parent_chunks,
        doc_path,
        *,
        document_id: str | None = None,
        source_name: str | None = None,
        user_id: str | None = None,
        visibility: str | None = None,
        category: str | None = None,
    ):
        normalized_document_id = (
            normalize_document_id(document_id, fallback=doc_path.stem)
            if document_id
            else None
        )
        normalized_user_id = normalize_user_id(user_id) if user_id is not None else None
        normalized_visibility = (
            normalize_visibility(visibility, user_id=normalized_user_id)
            if visibility is not None or user_id is not None
            else None
        )
        normalized_source_name = source_name or str(doc_path.stem) + ".pdf"

        for i, p_chunk in enumerate(parent_chunks):
            parent_id = build_parent_id(
                document_id=normalized_document_id,
                source_stem=doc_path.stem,
                index=i,
            )
            metadata = {
                "source": normalized_source_name,
                "parent_id": parent_id,
            }
            if normalized_document_id is not None:
                metadata["document_id"] = normalized_document_id
                metadata["source_name"] = normalized_source_name
            if normalized_user_id is not None:
                metadata["user_id"] = normalized_user_id
            if normalized_visibility is not None:
                metadata["visibility"] = normalized_visibility
            if category is not None:
                metadata["category"] = category

            p_chunk.metadata.update(metadata)
            
            all_parent_pairs.append((parent_id, p_chunk))
            all_child_chunks.extend(self.__child_splitter.split_documents([p_chunk]))
