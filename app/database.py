from typing import Optional, List
from google.cloud import firestore
from app.config import settings
from app.models import UserModel, RealEstateObjectModel, ConversationModel, MessageModel, RetailConceptModel
from app.repository import DataRepository

class FirestoreRepository(DataRepository):
    def __init__(self):
        # We assume the environment is properly authenticated (e.g. ADC)
        # or it uses FIRESTORE_PROJECT_ID.
        self.db = firestore.Client(
            project=settings.FIRESTORE_PROJECT_ID,
            database=settings.FIRESTORE_DATABASE_ID
        )
        self.users_col = self.db.collection("users")
        self.properties_col = self.db.collection("properties")
        self.conversations_col = self.db.collection("conversations")
        self.concepts_col = self.db.collection("retail_concepts")

    def get_user_by_username(self, username: str) -> Optional[UserModel]:
        docs = self.users_col.where("username", "==", username).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return UserModel(**data)
        return None

    def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        doc = self.users_col.document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return UserModel(**data)
        return None

    def create_user(self, user: UserModel) -> UserModel:
        doc_ref = self.users_col.document()
        user_data = user.model_dump(exclude={"id"})
        doc_ref.set(user_data)
        user.id = doc_ref.id
        return user

    def get_properties_for_user(self, user_id: str) -> List[RealEstateObjectModel]:
        docs = self.properties_col.where("user_id", "==", user_id).stream()
        props = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            props.append(RealEstateObjectModel(**data))
        return props

    def get_property_by_id_and_user(self, property_id: str, user_id: str) -> Optional[RealEstateObjectModel]:
        doc = self.properties_col.document(property_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("user_id") == user_id:
                data["id"] = doc.id
                return RealEstateObjectModel(**data)
        return None

    def get_property_by_id(self, property_id: str) -> Optional[RealEstateObjectModel]:
        doc = self.properties_col.document(property_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return RealEstateObjectModel(**data)
        return None

    def create_property(self, property: RealEstateObjectModel) -> RealEstateObjectModel:
        doc_ref = self.properties_col.document()
        data = property.model_dump(exclude={"id"})
        doc_ref.set(data)
        property.id = doc_ref.id
        return property

    def update_property(self, property: RealEstateObjectModel) -> RealEstateObjectModel:
        if not property.id:
            raise ValueError("Property must have an ID to be updated")
        doc_ref = self.properties_col.document(property.id)
        data = property.model_dump(exclude={"id"})
        doc_ref.update(data)
        return property

    def delete_property(self, property_id: str, user_id: str) -> bool:
        doc = self.properties_col.document(property_id).get()
        if doc.exists and doc.to_dict().get("user_id") == user_id:
            # Note: in Firestore, deleting a document doesn't delete subcollections.
            # But we don't have subcollections on properties right now.
            self.properties_col.document(property_id).delete()
            return True
        return False

    def get_conversations_for_property(self, property_id: str) -> List[ConversationModel]:
        docs = self.conversations_col.where("property_id", "==", property_id).stream()
        convs = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            convs.append(ConversationModel(**data))
        # Sort by created_at since firestore doesn't do it automatically without an index
        return sorted(convs, key=lambda c: c.created_at)

    def get_conversation_by_id_and_user(self, conversation_id: str, user_id: str) -> Optional[ConversationModel]:
        doc = self.conversations_col.document(conversation_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("user_id") == user_id:
                data["id"] = doc.id
                conv = ConversationModel(**data)
                # Load messages
                messages = []
                msg_docs = self.conversations_col.document(conversation_id).collection("messages").order_by("created_at").stream()
                for mdoc in msg_docs:
                    mdata = mdoc.to_dict()
                    mdata["id"] = mdoc.id
                    messages.append(MessageModel(**mdata))
                conv.messages = messages
                return conv
        return None

    def create_conversation(self, conversation: ConversationModel) -> ConversationModel:
        if not conversation.id:
            # We already have a default_factory for uuid4, but just in case
            doc_ref = self.conversations_col.document()
        else:
            doc_ref = self.conversations_col.document(conversation.id)
            
        data = conversation.model_dump(exclude={"id", "messages"})
        doc_ref.set(data)
        conversation.id = doc_ref.id
        return conversation

    def update_conversation(self, conversation: ConversationModel) -> ConversationModel:
        if not conversation.id:
            raise ValueError("Conversation must have an ID to be updated")
        doc_ref = self.conversations_col.document(conversation.id)
        data = conversation.model_dump(exclude={"id", "messages"})
        doc_ref.update(data)
        return conversation

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        doc = self.conversations_col.document(conversation_id).get()
        if doc.exists and doc.to_dict().get("user_id") == user_id:
            self.conversations_col.document(conversation_id).delete()
            # Also delete messages subcollection
            msgs = self.conversations_col.document(conversation_id).collection("messages").stream()
            for m in msgs:
                m.reference.delete()
            return True
        return False

    def add_message(self, message: MessageModel) -> MessageModel:
        doc_ref = self.conversations_col.document(message.conversation_id).collection("messages").document()
        data = message.model_dump(exclude={"id"})
        doc_ref.set(data)
        message.id = doc_ref.id
        return message

    def get_all_concepts(self) -> List[RetailConceptModel]:
        docs = self.concepts_col.stream()
        concepts = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            concepts.append(RetailConceptModel(**data))
        return sorted(concepts, key=lambda c: c.created_at)

    def get_concept_by_id(self, concept_id: str) -> Optional[RetailConceptModel]:
        doc = self.concepts_col.document(concept_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return RetailConceptModel(**data)
        return None

    def create_concept(self, concept: RetailConceptModel) -> RetailConceptModel:
        doc_ref = self.concepts_col.document()
        data = concept.model_dump(exclude={"id"})
        doc_ref.set(data)
        concept.id = doc_ref.id
        return concept

    def update_concept(self, concept: RetailConceptModel) -> RetailConceptModel:
        if not concept.id:
            raise ValueError("Concept must have an ID to be updated")
        doc_ref = self.concepts_col.document(concept.id)
        data = concept.model_dump(exclude={"id"})
        doc_ref.update(data)
        return concept

    def delete_concept(self, concept_id: str) -> bool:
        doc = self.concepts_col.document(concept_id).get()
        if doc.exists:
            self.concepts_col.document(concept_id).delete()
            return True
        return False

# Global instance
repo_instance = FirestoreRepository()

def get_repository() -> DataRepository:
    return repo_instance

def init_db() -> None:
    pass
