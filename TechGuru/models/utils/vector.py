from sqlalchemy import Column, Integer, Index, Float, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.types import TypeDecorator
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import mapped_column
from sqlalchemy import select
from sqlalchemy import ForeignKey
from models.utils.smart_uuid import SmartUUID

class VectorMixin:
    dimensions = 1536  # default dimension
    default_nearest = 'cosine'


    @declared_attr
    def embedding(cls):
        return mapped_column(Vector(cls.dimensions))

    
    def nearest(self, session, vector, limit=5, method=None, threshold = None):
        """
        Get nearest neighbors.
        Searches the namespace of the object from which you call this method; as such, any representative object from the target namespace can be used.
        returns a list of objects.
        """
        if method is None:
            method = self.default_nearest
        if method == 'cosine':
            return self.nearest_by_cosine(session, vector, limit, threshold)
        if method == 'l2':
            return self.nearest_by_l2(session, vector, limit, threshold)
        if method == 'inner_product':
            return self.nearest_by_inner_product(session, vector, limit, threshold)
        raise ValueError(f"Invalid nearest method: {method}")

    @declared_attr
    def namespace(cls):
        return Column(String, index=True, nullable=False, default=lambda: f"{cls.__name__}")

    def nearest_by_l2(self, session, vector, limit=5, threshold = None):
        """
        Get nearest neighbors by L2 distance using the instance's namespace.
        If this is slow, we can make the thresholding more efficient.
        session: sqlalchemy session
        vector: vector to compare to (dimensionality must match)
        limit: maximum number of results to return
        threshold: minimum distance to return

        """

        if threshold is not None:
            #only return ones where the distance is less than the threshold
            results = session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.l2_distance(vector)).limit(limit))
            return [result for result in results if result.embedding and result.embedding.l2_distance(vector) < threshold]
        
        #return results without threshold filtering
        return session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.l2_distance(vector)).limit(limit))

    def nearest_by_cosine(self, session, vector, limit=5, threshold=None):
        """
        Get nearest neighbors by cosine distance using the instance's namespace.
        Optionally filter results where the distance is less than a specified threshold.
        """
        if threshold is not None:
            # Only return items where the distance is less than the threshold
            results = session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.cosine_distance(vector)).limit(limit))
            return [result for result in results if result.embedding and result.embedding.cosine_distance(vector) < threshold]
    
        # Return results without threshold filtering
        return session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.cosine_distance(vector)).limit(limit))

    def nearest_by_inner_product(self, session, vector, limit=5, threshold=None):
        """
        Get nearest neighbors by max inner product using the instance's namespace.
        Optionally filter results where the inner product is greater than a specified threshold.
        """
        if threshold is not None:
            # Only return items where the inner product is greater than the threshold
            results = session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.inner_product(vector).desc()).limit(limit))
            return [result for result in results if result.embedding and result.embedding.inner_product(vector) > threshold]
        
        # Return results without threshold filtering
        return session.scalars(select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.inner_product(vector).desc()).limit(limit))

    
    @declared_attr
    def __declare_last__(cls):
        """Create an index on the embedding column. Create another on the namespace column."""
        if hasattr(cls, '__tablename__') and hasattr(cls, 'embedding'):
            Index(
                f'idx_{cls.__tablename__}_embedding', 
                cls.embedding, 
                postgresql_using='ivfflat',
                postgresql_with={'lists': 100},
                postgresql_ops={'embedding': 'vector_cosine_ops'})
            Index(f'idx_{cls.__tablename__}_namespace', cls.namespace)
'''
# Usage Example
class Item(VectorMixin, Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    namespace = 'my_namespace'
    dimensions = 1536
'''

class ProjectVectorMixin(VectorMixin):
    '''
    same as VectorMixin, but with project_id for namespace.
    '''

    project_id = Column(SmartUUID(), ForeignKey('project.id'), nullable=False)

    @declared_attr
    def namespace(cls):
        return Column(String, index=True, nullable=False, default=lambda: f"{cls.project_id}_{cls.__name__}")
    
class DCOVectorMixin(VectorMixin):
    '''
    '''
    namespace_id = Column(SmartUUID(), ForeignKey('dco_semantic_namespace.id'), nullable=False)
    dc_object_id = Column(SmartUUID(), ForeignKey('dc_object.id'), nullable=False)

    @declared_attr
    def namespace(cls):
        return Column(String, index=True, nullable=False, default=lambda: f"{cls.namespace_id}_{cls.dc_object_id}_{cls.__name__}")