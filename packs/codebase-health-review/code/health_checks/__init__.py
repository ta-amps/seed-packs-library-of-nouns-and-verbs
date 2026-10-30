"""Health checks for the codebase health review seed pack: a TODO and FIXME ager and a swallowed-exception finder.

Standard library only. The ager reads files and, when the folder is a git work tree, runs read-only
`git rev-parse` and `git blame`; the finder reads Python source with ast and never imports or runs it.
Nothing here opens a network connection, calls a model or writes a file; the command line prints JSON.
"""

from .swallowed import ACT, CLASSES, classify, find_swallowed, scan_source
from .todos import BUCKETS, age_todos, bucket, markers, parse_porcelain

__all__ = ["ACT", "BUCKETS", "CLASSES", "age_todos", "bucket", "classify", "find_swallowed", "markers",
           "parse_porcelain", "scan_source"]
__version__ = "0.1.0"
