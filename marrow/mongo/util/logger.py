# encoding: utf-8

"""

Example configuration:

{
	'version': 1,
	'handlers': {
			'console': {
					'class': 'logging.StreamHandler',
					'formatter': 'json',
					'level': 'DEBUG' if __debug__ else 'INFO',
					'stream': 'ext://sys.stdout',
				}
		},
	'loggers': {
			'web': {
					'level': 'DEBUG' if __debug__ else 'WARN',
					'handlers': ['console'],
					'propagate': False,
				},
		},
	'root': {
			'level': 'INFO' if __debug__ else 'WARN',
			'handlers': ['console']
		},
	'formatters': {
			'json': {
					'()': 'web.contentment.util.JSONFormatter',
				}
		},
}


"""

from __future__ import unicode_literals

import logging
import datetime
from bson.json_util import dumps
from pymongo import MongoClient
from pytz import utc
from tzlocal import get_localzone

try:
	from pygments import highlight as _highlight
	from pygments.formatters import Terminal256Formatter
	from pygments.lexers.data import JsonLexer
except ImportError:
	_highlight = None



DEFAULT_PROPERTIES = logging.LogRecord('', '', '', '', '', '', '', '').__dict__.keys()
LOCAL_TZ = get_localzone()



class JSONFormatter(logging.Formatter):
	REPR_FAILED = 'REPR_FAILED'
	BASE_TYPES = (int, float, bool, bytes, str, list, dict)
	EXCLUDE = {
		# Python 2/3
		'args', 'name', 'msg', 'levelname', 'levelno', 'pathname', 'filename',
		'module', 'exc_info', 'exc_text', 'lineno', 'funcName', 'created',
		'msecs', 'relativeCreated', 'thread', 'threadName', 'processName',
		'process', 'getMessage', 'message', 'asctime',
		
		# Python 3
		'stack_info',
	}
	
	def __init__(self, highlight=None, **kwargs):
		if __debug__:
			kwargs.setdefault('format', '%(asctime)s\t%(levelname)s\t%(name)s:%(funcName)s:%(lineno)s\t%(message)s')
		else:
			kwargs.setdefault('format', '%(levelname)s %(name)s:%(funcName)s:%(lineno)s %(message)s')
		super(JSONFormatter, self).__init__(**kwargs)
		self.highlight = (__debug__ if highlight is None else highlight) and _highlight
	
	def _default(self, value):
		try:
			return str(value)
		except:
			try:
				return repr(value)
			except:
				return self.REPR_FAILED
	
	def jsonify(self, record, **kw):
		extra = {}
		
		for attr, value in record.__dict__.items():
			if attr in self.EXCLUDE: continue
			extra[attr] = value
		
		if extra:
			try:
				return dumps(extra, skipkeys=True, sort_keys=True, default=self._default, **kw)
			except Exception as e:
				return dumps({'__error': repr(e)}, **kw)
		
		return ''
	
	def format(self, record):
		formatted = logging.Formatter.format(self, record)
		json = self.jsonify(
				record,
				indent = '\t' if __debug__ else '',
				separators = (',', ': ') if __debug__ else (',', ':'),
			)
		
		if json:
			if self.highlight:
				return '\n'.join([formatted, _highlight(json, JsonLexer(tabsize=4), Terminal256Formatter(style='monokai')).strip()])
			
			return '\n'.join([formatted, json]).strip()
		
		return formatted


class MongoFormatter(logging.Formatter):
	def format(self, record):
		time = datetime.fromtimestamp(record.created),
		time = LOCAL_TZ.localize(time).astimezone(utc)
		
		document = dict(
				service = record.name,
				level = record.levelno,
				message = record.getMessage(),  # TODO: super() this?
				
				time = time,
				process = dict(
						identifier = record.process,
						name = record.processName,
					),
				thread = dict(
						identifier = record.thread,
						name = record.threadName,
					),
				location = dict(
						path = record.pathname,
						line = record.lineno,
						module = record.module,
						function = record.funcName,
					),
			)
		
		if record.exc_info is not None:
			document['exception'] = dict(
					message = str(record.exc_info[1]),
					trace = self.formatException(record.exc_info)
				)
		
		# Standard document decorated with extra contextual information
		
		if len(DEFAULT_PROPERTIES) != len(record.__dict__):
			extras = set(record.__dict__).difference(set(DEFAULT_PROPERTIES))
			for name in extras:
				document[name] = record.__dict__[name]
		
		return document


class MongoHandler(logging.Handler):
	def __init__(self, uri, collection, level=logging.NOTSET, quiet=False):
		logging.Handler.__init__(level)
		
		if quiet:
			self.lock = None  # We don't require I/O locking if we aren't touching stderr.
		
		client = self.client = MongoClient(uri)
		database = client.get_default_database()
		self.collection = database[collection]
		
		self.buffer = []
		self.formatter = MongoFormatter()  # We default to our standard record encoding.
	
	def emit(self, record):
		try:
			document = self.format(record)
		except:
			self.handleError(record)
		
		try:
			result = self.collection.insert_one(document)
		except:
			self.handleError(record)
		
		document['_id'] = result.inserted_id
		if self.quiet: return

