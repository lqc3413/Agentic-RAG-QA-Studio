import config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

class VectorDbManager:
    """管理本地 Qdrant、dense embedding 和 sparse BM25 检索配置。"""
    __client: QdrantClient
    __sparse_embeddings: FastEmbedSparse
    def __init__(self):
        """初始化本地 Qdrant 客户端和检索模型。"""
        self.__client = QdrantClient(path=config.QDRANT_DB_PATH)
        self.__dense_embeddings = self.__create_dense_embeddings()
        self.__sparse_embeddings = FastEmbedSparse(model_name=config.SPARSE_MODEL)

    def __create_dense_embeddings(self):
        """创建 dense embedding 模型。"""
        if config.EMBEDDING_PROVIDER == "openai_compatible":
            if not config.EMBEDDING_API_KEY:
                raise ValueError(
                    "EMBEDDING_API_KEY, ali_api_key, or DASHSCOPE_API_KEY is required "
                    "for openai_compatible embeddings."
                )

            return OpenAIEmbeddings(
                model=config.DENSE_MODEL,
                api_key=config.EMBEDDING_API_KEY,
                base_url=config.EMBEDDING_API_BASE_URL,
                check_embedding_ctx_length=False,
            )

        if config.EMBEDDING_PROVIDER == "huggingface":
            return HuggingFaceEmbeddings(model_name=config.DENSE_MODEL)

        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {config.EMBEDDING_PROVIDER}")

    def create_collection(self, collection_name):
        """创建存放 child chunks 的 Qdrant collection。"""
        if not self.__client.collection_exists(collection_name):
            print(f"Creating collection: {collection_name}...")
            self.__client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=len(self.__dense_embeddings.embed_query("test")), distance=qmodels.Distance.COSINE),
                sparse_vectors_config={config.SPARSE_VECTOR_NAME: qmodels.SparseVectorParams()},
            )
            print(f"[OK] Collection created: {collection_name}")
        else:
            print(f"[OK] Collection already exists: {collection_name}")

    def delete_collection(self, collection_name):
        try:
            if self.__client.collection_exists(collection_name):
                print(f"Removing existing Qdrant collection: {collection_name}")
                self.__client.delete_collection(collection_name)
        except Exception as e:
            print(f"Warning: could not delete collection {collection_name}: {e}")

    def get_collection(self, collection_name) -> QdrantVectorStore:
        """返回 LangChain 使用的 hybrid QdrantVectorStore。"""
        try:
            return QdrantVectorStore(
                    client=self.__client,
                    collection_name=collection_name,
                    embedding=self.__dense_embeddings,
                    sparse_embedding=self.__sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID,
                    sparse_vector_name=config.SPARSE_VECTOR_NAME
                )
        except Exception as e:
            print(f"Unable to get collection {collection_name}: {e}")

    def delete_document_vectors(self, collection_name: str, *, document_id: str, user_id: str) -> None:
        self._delete_by_filter(
            collection_name,
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="metadata.user_id",
                        match=qmodels.MatchValue(value=str(user_id)),
                    ),
                    qmodels.FieldCondition(
                        key="metadata.document_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    ),
                ]
            ),
        )

    def delete_private_vectors_for_user(self, collection_name: str, *, user_id: str) -> None:
        self._delete_by_filter(
            collection_name,
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="metadata.user_id",
                        match=qmodels.MatchValue(value=str(user_id)),
                    ),
                    qmodels.FieldCondition(
                        key="metadata.visibility",
                        match=qmodels.MatchValue(value="private"),
                    ),
                ]
            ),
        )

    def _delete_by_filter(self, collection_name: str, payload_filter: qmodels.Filter) -> None:
        try:
            if not self.__client.collection_exists(collection_name):
                return
            self.__client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(filter=payload_filter),
            )
        except Exception as e:
            print(f"Warning: could not delete vectors from {collection_name}: {e}")
