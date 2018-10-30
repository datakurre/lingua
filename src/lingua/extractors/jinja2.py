# Derivate of BSD licensed jinja2/ext.py by (c) 2017 by the Jinja Team
from jinja2 import nodes
from jinja2._compat import string_types
from jinja2.defaults import BLOCK_END_STRING, BLOCK_START_STRING, \
    COMMENT_END_STRING, COMMENT_START_STRING, KEEP_TRAILING_NEWLINE, \
    LINE_COMMENT_PREFIX, LINE_STATEMENT_PREFIX, LSTRIP_BLOCKS, \
    NEWLINE_SEQUENCE, TRIM_BLOCKS, VARIABLE_END_STRING, VARIABLE_START_STRING
from jinja2.environment import Environment
from jinja2.exceptions import TemplateSyntaxError
from jinja2.ext import InternationalizationExtension
from jinja2.utils import import_string

from . import EXTRACTORS
from . import EXTENSIONS
from . import Extractor
from . import Keyword
from . import Message
from . import update_keywords
from .python import KEYWORDS

# the only real useful gettext functions for a Jinja template.  Note
# that ugettext must be assigned to gettext as Jinja doesn't support
# non unicode strings.
GETTEXT_FUNCTIONS = ('_', 'gettext', 'ngettext')


def extract_from_ast(node, gettext_functions=GETTEXT_FUNCTIONS):
    """Extract localizable strings from the given template node.

    For every string found this function yields a ``(lineno, msgid, default)``
    tuple, where:

    * ``lineno`` is the number of the line on which the string was found
    * ``msgid`` is the msgid or string string itself (a ``unicode`` object)
    * ``default`` is value of the ``default`` keyword argument for the
      function.
    """
    for node in node.find_all(nodes.Call):
        if not isinstance(node.node, nodes.Name) or \
           node.node.name not in gettext_functions:
            continue

        msgid = u''
        default = u''

        for arg in node.args:
            if isinstance(arg, nodes.Const) and \
               isinstance(arg.value, string_types):
                msgid = arg.value

        for arg in node.kwargs:
            if arg.key == 'default' and \
                    isinstance(arg.value.value, string_types):
                default = arg.value.value

        yield node.lineno, msgid, default


class Jinja2Extractor(Extractor):
    """Jinja2 sources"""
    extensions = ['.jinja2']

    def __call__(self, filename, options, fileobj=None, firstline=0):
        self.keywords = KEYWORDS.copy()
        self.keywords['_'] = Keyword('_')
        update_keywords(self.keywords, options.keywords)

        extensions = set()
        for extension in getattr(options, 'extensions', '').split(','):
            extension = extension.strip()
            if not extension:
                continue
            extensions.add(import_string(extension))

        if InternationalizationExtension not in extensions:
            extensions.add(InternationalizationExtension)

        def getbool(options, key, default=False):
            return getattr(options, key, str(default)).lower() in \
                   ('1', 'on', 'yes', 'true')

        silent = getbool(options, 'silent', True)
        environment = Environment(
            getattr(options, 'block_start_string', BLOCK_START_STRING),
            getattr(options, 'block_end_string', BLOCK_END_STRING),
            getattr(options, 'variable_start_string', VARIABLE_START_STRING),
            getattr(options, 'variable_end_string', VARIABLE_END_STRING),
            getattr(options, 'comment_start_string', COMMENT_START_STRING),
            getattr(options, 'comment_end_string', COMMENT_END_STRING),
            getattr(options, 'line_statement_prefix', LINE_STATEMENT_PREFIX),
            getattr(options, 'line_comment_prefix', LINE_COMMENT_PREFIX),
            getbool(options, 'trim_blocks', TRIM_BLOCKS),
            getbool(options, 'lstrip_blocks', LSTRIP_BLOCKS),
            NEWLINE_SEQUENCE,
            getbool(options, 'keep_trailing_newline', KEEP_TRAILING_NEWLINE),
            frozenset(extensions),
            cache_size=0,
            auto_reload=False
        )

        if getbool(options, 'trimmed'):
            environment.policies['ext.i18n.trimmed'] = True
        if getbool(options, 'newstyle_gettext'):
            environment.newstyle_gettext = True

        if fileobj is None:
            with open(filename, 'rb') as fb:
                source = fb.read().decode(getattr(options, 'encoding', 'utf-8'))  # noqa: E501
        else:
            source = fileobj.read().decode(getattr(options, 'encoding', 'utf-8'))  # noqa: E501

        try:
            node = environment.parse(source)
        except TemplateSyntaxError:
            if not silent:
                raise
            # skip templates with syntax errors
            return

        for lineno, msgid, default in extract_from_ast(node, self.keywords):
            comment = u'Default: %s' % default if default else u''
            yield Message(None, msgid, None, [], comment, u'',
                          (filename, firstline + lineno))


def register_jinja2_plugin():
    EXTRACTORS['jinja2'] = Jinja2Extractor()
    EXTENSIONS['.jinja2'] = 'jinja2'
