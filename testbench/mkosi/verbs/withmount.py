# SPDX-License-Identifier: LGPL-2.1+

import os

from ..luks import luks_setup_all
from ..types import CommandLineArguments
from ..ui import run_visible
from .build import (
    attach_image_loopback,
    determine_partition_table,
    init_namespace,
    mount_image,
    setup_workspace,
)

NEEDS_ROOT = True
NEEDS_BUILD = True

def do(args: CommandLineArguments) -> None:
    init_namespace(args)
    determine_partition_table(args)
    with setup_workspace(args) as workspace:
        with open(args.output, 'rb') as raw:
            with attach_image_loopback(args, raw) as loopdev:
                with luks_setup_all(args, loopdev, False) as (encrypted_root, encrypted_home, encrypted_srv):
                    with mount_image(args, workspace, loopdev, encrypted_root, encrypted_home, encrypted_srv):
                        run_visible(args.cmdline, cwd=os.path.join(workspace, "root"), check=True)
