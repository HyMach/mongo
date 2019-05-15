from collections.abc import Iterable, Mapping

from ... import Field
from ..types import check_argument_types, Set
from .base import _HasKind, _CastingKind


class Array(_HasKind, _CastingKind, Field):
	__foreign__: str = 'array'
	__allowed_operators__: Set[str] = {'#array', '$elemMatch', '#rel', '$eq'}
	
	class List(list):
		"""Placeholder list shadow class to identify already-cast arrays."""
		
		@classmethod
		def new(cls):
			return cls()
	
	def __init__(self, *args, **kw):
		if kw.get('assign', False):
			kw.setdefault('default', self.List.new)
		
		super(Array, self).__init__(*args, **kw)
	
	def to_native(self, obj, name:str, value:Iterable) -> list:
		"""Transform the MongoDB value into a Marrow Mongo value."""
		
		if isinstance(value, self.List):
			return value
		
		result = self.List(super().to_native(obj, name, i) for i in value)
		obj.__data__[self.__name__] = result
		
		return result
	
	def to_foreign(self, obj, name:str, value) -> list:
		"""Transform to a MongoDB-safe value."""
		
		if isinstance(value, Iterable) and not isinstance(value, Mapping):
			return self.List(super().to_foreign(obj, name, i) for i in value)
		
		return super().to_foreign(obj, name, value)
