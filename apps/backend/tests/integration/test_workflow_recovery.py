import pytest
import uuid
from datetime import UTC, datetime, timedelta
from app.services.recovery_service import WorkflowRecoveryService
from app.models.print_job import PrintJob
from app.repositories.print_job_repository import PrintJobRepository

pytestmark = pytest.mark.asyncio

async def test_recovery_payment_timeout(db_session):
    # Create a job that is PAYMENT_PENDING but older than 15 minutes
    repo = PrintJobRepository(db_session)
    import uuid
    dummy_file_id = uuid.uuid4()
    job = await repo.create(
        session_id="test_session_123",
        uploaded_file_id=dummy_file_id,
        color_mode="BW",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_selected=1,
        pages_per_sheet=1,
        page_range=None,
        orientation="portrait",
        subtotal_inr=10.0,
        gst_inr=1.8,
        total_inr=11.8,
        idempotency_key="test_rec_payment",
        correlation_id="test_rec_corr_1"
    )
    
    await repo.transition(job.id, "VALIDATED")
    await repo.transition(job.id, "PAYMENT_PENDING")
    
    # Manually backdate the updated_at timestamp
    past_date = datetime.now(tz=UTC) - timedelta(minutes=20)
    job.updated_at = past_date
    await db_session.commit()
    
    # Run recovery
    service = WorkflowRecoveryService(db_session)
    recovered = await service.recover_stuck_jobs()
    
    # Assert
    assert recovered >= 1
    
    await db_session.refresh(job)
    assert job.status == "CANCELLED"


async def test_recovery_assigned_timeout(db_session):
    # Create a job that is ASSIGNED but older than 5 minutes
    repo = PrintJobRepository(db_session)
    job = await repo.create(
        session_id="test_session_123",
        uploaded_file_id=uuid.uuid4(),
        color_mode="BW",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_selected=1,
        pages_per_sheet=1,
        page_range=None,
        orientation="portrait",
        subtotal_inr=10.0,
        gst_inr=1.8,
        total_inr=11.8,
        idempotency_key="test_rec_assigned",
        correlation_id="test_rec_corr_2"
    )
    
    await repo.transition(job.id, "VALIDATED")
    await repo.transition(job.id, "PAYMENT_PENDING")
    await repo.transition(job.id, "PAYMENT_SUCCESS")
    await repo.transition(job.id, "QUEUED")
    await repo.transition(job.id, "ASSIGNED")
    
    # Manually backdate
    past_date = datetime.now(tz=UTC) - timedelta(minutes=10)
    job.updated_at = past_date
    await db_session.commit()
    
    # Run recovery
    service = WorkflowRecoveryService(db_session)
    recovered = await service.recover_stuck_jobs()
    
    # Assert
    assert recovered >= 1
    
    await db_session.refresh(job)
    assert job.status == "QUEUED"
    assert job.retry_count == 1
    

async def test_recovery_printing_timeout(db_session):
    # Create a job that is PRINTING but older than 10 minutes
    repo = PrintJobRepository(db_session)
    job = await repo.create(
        session_id="test_session_123",
        uploaded_file_id=uuid.uuid4(),
        color_mode="BW",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_selected=1,
        pages_per_sheet=1,
        page_range=None,
        orientation="portrait",
        subtotal_inr=10.0,
        gst_inr=1.8,
        total_inr=11.8,
        idempotency_key="test_rec_printing",
        correlation_id="test_rec_corr_3"
    )
    
    await repo.transition(job.id, "VALIDATED")
    await repo.transition(job.id, "PAYMENT_PENDING")
    await repo.transition(job.id, "PAYMENT_SUCCESS")
    await repo.transition(job.id, "QUEUED")
    await repo.transition(job.id, "ASSIGNED")
    await repo.transition(job.id, "DOWNLOADING")
    await repo.transition(job.id, "READY_TO_PRINT")
    await repo.transition(job.id, "PRINTING")
    
    # Manually backdate
    past_date = datetime.now(tz=UTC) - timedelta(minutes=15)
    job.updated_at = past_date
    await db_session.commit()
    
    # Run recovery
    service = WorkflowRecoveryService(db_session)
    recovered = await service.recover_stuck_jobs()
    
    # Assert
    assert recovered >= 1
    
    await db_session.refresh(job)
    assert job.status == "FAILED"


async def test_recovery_multiple_stuck_jobs(db_session):
    # Verify that recovering multiple stuck jobs in a single run does not raise MissingGreenlet
    repo = PrintJobRepository(db_session)
    past_date = datetime.now(tz=UTC) - timedelta(minutes=20)

    job1 = await repo.create(
        session_id="test_session_multi_1",
        uploaded_file_id=uuid.uuid4(),
        color_mode="BW",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_selected=1,
        pages_per_sheet=1,
        page_range=None,
        orientation="portrait",
        subtotal_inr=10.0,
        gst_inr=1.8,
        total_inr=11.8,
        idempotency_key="test_rec_multi_1",
        correlation_id="test_rec_corr_m1"
    )
    await repo.transition(job1.id, "VALIDATED")
    await repo.transition(job1.id, "PAYMENT_PENDING")
    job1.updated_at = past_date

    job2 = await repo.create(
        session_id="test_session_multi_2",
        uploaded_file_id=uuid.uuid4(),
        color_mode="BW",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_selected=1,
        pages_per_sheet=1,
        page_range=None,
        orientation="portrait",
        subtotal_inr=10.0,
        gst_inr=1.8,
        total_inr=11.8,
        idempotency_key="test_rec_multi_2",
        correlation_id="test_rec_corr_m2"
    )
    await repo.transition(job2.id, "VALIDATED")
    await repo.transition(job2.id, "PAYMENT_PENDING")
    job2.updated_at = past_date

    await db_session.commit()

    service = WorkflowRecoveryService(db_session)
    recovered = await service.recover_stuck_jobs()

    assert recovered >= 2

    await db_session.refresh(job1)
    await db_session.refresh(job2)
    assert job1.status == "CANCELLED"
    assert job2.status == "CANCELLED"

