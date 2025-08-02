from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.models.validation_transaction import ValidationTransaction, ValidationStatus

class ValidationTransactionRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_transaction(
        self, *,
        transaction_id: uuid.UUID,
        tenant_id: str,
        user_id: str,
        username: str,
        profile_id: int | None,
        filename: str,
        request_key: str
    ) -> ValidationTransaction:
        
        db_transaction = ValidationTransaction(
            id=transaction_id,
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            partner_profile_id=profile_id,
            original_filename=filename,
            request_object_key=request_key,
            status=ValidationStatus.PENDING
        )
        self.db.add(db_transaction)
        await self.db.commit()
        await self.db.refresh(db_transaction)
        return db_transaction

    async def update_transaction_acks_and_status(
        self, *,
        transaction_id: uuid.UUID,
        status: ValidationStatus,
        ta1_key: str | None,
        ack999_key: str | None
    ):
        db_transaction = await self.db.get(ValidationTransaction, transaction_id)
        if db_transaction:
            db_transaction.status = status
            db_transaction.ta1_object_key = ta1_key
            db_transaction.response_999_object_key = ack999_key
            await self.db.commit()