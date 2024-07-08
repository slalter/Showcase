from celery import Celery
from models.database import Session, Base
from models.utils.dcategory import CategoryQueue, CategoryMaster
from app import celery
from sqlalchemy.exc import SQLAlchemyError

@celery.task
def process_queue():
    session = Session()
    
    with session:
        processed = set()
        errors = []
        while True:
            entry = session.query(CategoryQueue).order_by(CategoryQueue.id).with_for_update(skip_locked=True).first()
            if not entry or entry.id in processed:
                break
            try:
                category = session.query(CategoryMaster).filter_by(id=entry.category_id).first()
                if category:
                    # Process the category and update as necessary
                    new_category_name = entry.original_value.replace(' ', '_').lower()
                    if new_category_name != category.category_name:
                        category.category_name = new_category_name
                        session.commit()

                    # Update the original row reference if it exists
                    table_name, row_id = entry.row_reference.split(":")
                    table = Base.metadata.tables[table_name]
                    stmt = table.update().where(table.c.id == row_id).values({entry.original_value: new_category_name})
                    session.execute(stmt)
                    session.commit()

                processed.add(entry.id)

                # Remove the processed entry
                session.delete(entry)
                session.commit()

            except SQLAlchemyError as e:
                # If an error occurs, re-insert the entry at the back of the line, and add it to the processed set so we don't keep trying to process it
                # delete the entry
                new_entry = CategoryQueue(
                    category_id=entry.category_id,
                    original_value=entry.original_value,
                    row_reference=entry.row_reference
                )
                session.add(new_entry)
                session.commit()
                session.delete(entry)
                session.commit()
                processed.add(new_entry.id)
                errors.append((new_entry.id, str(e)))
        entry = session.query(CategoryQueue).order_by(CategoryQueue.id).with_for_update(skip_locked=True).first()
        
        if errors:
            raise Exception(f"Errors occurred during processing: {errors}")


#celery.conf.beat_schedule = {
#    'process-queue-every-second': {
#        'task': 'tasks.cron.dcategory.process_queue',
#        'schedule': 1.0,
#    },
#}
