from sqlalchemy import Column, Integer, Index, Float, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.types import TypeDecorator
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import mapped_column
from sqlalchemy import select
from sqlalchemy import ForeignKey
from models.utils.smart_uuid import SmartUUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import mapped_column
from sqlalchemy import Column, String, select, Index
from sqlalchemy.orm import sessionmaker
import numpy as np
from packages.guru.GLLM import LLM
class VectorMixin:
    '''
    vectormixins need to handle making their own embeddings.
    '''
    dimensions = 1536  # default dimension
    default_nearest = 'cosine'

    @declared_attr
    def embedding(cls):
        return mapped_column(Vector(cls.dimensions))

    @declared_attr
    def namespace(cls):
        return Column(String, index=True, nullable=False, default=lambda: f"{cls.__name__}")

    def nearest(self, session, vector, limit=5, method=None, threshold=None, with_scores=False):
        """
        Get nearest neighbors.
        Searches the namespace of the object from which you call this method; as such, any representative object from the target namespace can be used.
        Returns a list of objects or item:score pairs if with_scores is True.
        """
        if method is None:
            method = self.default_nearest
        if method == 'cosine':
            return self.nearest_by_cosine(session, vector, limit, threshold, with_scores)
        if method == 'l2':
            return self.nearest_by_l2(session, vector, limit, threshold, with_scores)
        if method == 'inner_product':
            return self.nearest_by_inner_product(session, vector, limit, threshold, with_scores)
        raise ValueError(f"Invalid nearest method: {method}")

    def nearest_by_l2(self, session, vector, limit=5, threshold=None, with_scores=False):
        """
        Get nearest neighbors by L2 distance using the instance's namespace.
        If this is slow, we can make the thresholding more efficient.
        session: sqlalchemy session
        vector: vector to compare to (dimensionality must match)
        limit: maximum number of results to return
        threshold: minimum distance to return
        Returns a list of objects or score:item pairs if with_scores is True.
        """
        query = select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.l2_distance(vector)).limit(limit)
        results = session.scalars(query).all()

        if threshold is not None:
            results = [result for result in results if result.embedding and result.embedding.l2_distance(vector) < threshold]

        if with_scores:
            return [(result, result.embedding.l2_distance(vector)) for result in results]
        return results

    def nearest_by_cosine(self, session, vector, limit=5, threshold=None, with_scores=False):
        """
        Get nearest neighbors by cosine distance using the instance's namespace.
        Optionally filter results where the distance is less than a specified threshold.
        Returns a list of objects or score:item pairs if with_scores is True.
        """
        results = session.query(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.cosine_distance(vector)).limit(limit).all()
        if threshold is not None:
            results = [result for result in results if result.embedding and LLM.compare(result.embedding, self.embedding) < threshold]

        if with_scores:
            return [(result, LLM.compare(result.embedding, self.embedding)) for result in results]
        return results

    def nearest_by_inner_product(self, session, vector, limit=5, threshold=None, with_scores=False):
        """
        Get nearest neighbors by max inner product using the instance's namespace.
        Optionally filter results where the inner product is greater than a specified threshold.
        Returns a list of objects or score:item pairs if with_scores is True.
        """
        query = select(type(self)).filter(type(self).namespace == self.namespace).order_by(type(self).embedding.inner_product(vector).desc()).limit(limit)
        results = session.scalars(query).all()

        if threshold is not None:
            results = [result for result in results if result.embedding and result.embedding.inner_product(vector) > threshold]

        if with_scores:
            return [(result, result.embedding.inner_product(vector)) for result in results]
        return results

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