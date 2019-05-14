from bson.int64 import Int64

from .number import Number


class Long(Number):
	__foreign__ = 'long'
	
	def to_foreign(self, obj, name:str, value) -> Int64:  # pylint:disable=unused-argument
		return Int64(int(value))
