# SPDX-License-Identifier: LGPL-2.1+
#
# This file is based on sshuttle's ssh.py

# Note that this module strictly uses modern 'importlib' (not 'imp')
# because it needs to work as a zipapp or in any other packaging
# mechanism.

import importlib
import pickle
import pkgutil
from io import BytesIO
from subprocess import run
from typing import Any, BinaryIO, Callable, List, Optional, Set

# The complement to serialize_module()/serialize_end() is
# deserialize_all() in docker_inside.py.

def serialize_module(writer: BinaryIO, module_name: str) -> None:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise RuntimeError('Unknown module "%s".' % module_name)
    assert isinstance(spec.loader, importlib.abc.InspectLoader)
    body = spec.loader.get_source(module_name)
    assert body is not None
    writer.write(b'%s\n%d\n%s' % (
        module_name.encode('utf-8'),
        len(body.encode('utf-8')),
        body.encode('utf-8')))

def serialize_end(writer: BinaryIO) -> None:
    writer.write(b'\n')

def run_in_docker(fn: Callable[..., None], args: List[Any], module_names: List[str]=[]) -> None:

    module_names = module_names + [fn.__module__]

    # We do this in multiple stages because: The first stage (whether
    # or not there are more after it) is sent over argv, which means
    # that it is likely to appear in-its-entirety in debug messages
    # and such, so we really want it to be short.

    # Stage 2:
    #  1. Read a series of serialized modules from stdin
    #  2. Read the function's __module__/__name__/arguments from stdin
    #  3. `from __module__ import __name__` and call it
    _stage2: Optional[bytes] = pkgutil.get_data(__package__, 'docker_stage2.py')
    assert _stage2 is not None
    stage2: bytes = _stage2

    # Stage 1: But stage2 is kinda big, so we don't want to send it over argv:
    #  1. Read stage2 from stdin and execute it
    stage1: bytes = ("import os, sys; sys.stdin = os.fdopen(0, 'rb'); exec(compile(sys.stdin.read(%d), 'docker_stage2.py', 'exec'))" % len(stage2)).encode("utf-8")

    stdin = BytesIO()
    # Send stage2 for stage1 to read
    stdin.write(stage2)
    # Send modules for stage2 to read
    done: Set[str] = set()
    for module_name in module_names:
        if module_name in done:
            continue
        serialize_module(stdin, module_name)
        done.add(module_name)
    serialize_end(stdin)
    # Send function's __module__/__name__/arguments for stage2 to read
    stdin.write(("%s\n%s\n" % (fn.__module__, fn.__name__)).encode("utf-8"))
    pickle.dump(args, stdin)

    run(["docker", "run", "-i", "fedora", "python3", "-c", stage1],
        input=stdin.getvalue(), check=True)
