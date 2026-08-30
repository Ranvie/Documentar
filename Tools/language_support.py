from __future__ import annotations

import os
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))     # Tools
sys.path.insert(0, os.path.join(_TOOLS_DIR, "dependency"))  # onde dependency_parsers/dependency_resolvers moram hoje

from dependency_parsers.python_parser import PythonParser
from dependency_parsers.php_parser import PhpParser
from dependency_parsers.javascript_parser import JavaScriptParser
from dependency_resolvers.php_resolver import PhpResolver
from dependency_resolvers.javascript_resolver import JavaScriptResolver
from dependency_resolvers.python_resolver import PythonResolver


class LanguageSupport:
    def __init__(self):
        self._parsers = {
            "python": PythonParser(),
            "php": PhpParser(),
            "javascript": JavaScriptParser(),
        }
        self._resolvers = {
            "php": PhpResolver(),
            "javascript": JavaScriptResolver(),
            "python": PythonResolver(),
        }

    def parsers(self) -> dict:
        return self._parsers

    def supported_languages(self) -> dict:
        return self._resolvers


LANGUAGE_SUPPORT = LanguageSupport()
