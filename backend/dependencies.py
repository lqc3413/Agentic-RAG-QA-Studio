_rag_system = None
_document_manager = None
_chat_service = None
_qa_record_manager = None
_user_manager = None


def get_rag_system():
    global _rag_system

    if _rag_system is None:
        from core.rag_system import RAGSystem
        _rag_system = RAGSystem()
        
    if not _rag_system.agent_graph:
        _rag_system.initialize()

    return _rag_system


async def init_rag_system_async():
    global _rag_system

    if _rag_system is None:
        from core.rag_system import RAGSystem
        _rag_system = RAGSystem()
        
    if not _rag_system.agent_graph:
        await _rag_system.initialize_async()
        
    return _rag_system



def get_document_manager():
    global _document_manager

    if _document_manager is None:
        from core.document_manager import DocumentManager

        _document_manager = DocumentManager(get_rag_system())

    return _document_manager


def get_chat_service():
    global _chat_service

    if _chat_service is None:
        from backend.services.chat_service import ChatService

        _chat_service = ChatService(get_rag_system())

    return _chat_service


def get_qa_record_manager():
    global _qa_record_manager

    if _qa_record_manager is None:
        from db.qa_record_manager import QARecordManager

        _qa_record_manager = QARecordManager()

    return _qa_record_manager


def get_user_manager():
    global _user_manager

    if _user_manager is None:
        from db.user_manager import UserManager

        _user_manager = UserManager()
        _seed_admin_user(_user_manager)

    return _user_manager


def _seed_admin_user(user_manager):
    import os
    from backend.security import hash_password

    username = (os.environ.get("ADMIN_USERNAME") or "").strip()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not username or not password:
        return

    if user_manager.get_by_username(username):
        return

    user_manager.create_user(
        username=username,
        password_hash=hash_password(password),
        role="admin",
    )


_agent_memory_manager = None


def get_agent_memory_manager():
    global _agent_memory_manager

    if _agent_memory_manager is None:
        from db.agent_memory_manager import AgentMemoryManager

        _agent_memory_manager = AgentMemoryManager()

    return _agent_memory_manager
